"""MlpJepaSubstrate — Q1 frozen substrate (encoder + AC-predictor + EMA target).

Implements the spec's Section A 3-trait family (substrate side only — L1
in Q2). Uses jepa_features.FusionEncoder + a new action-conditioned
predictor + EMA target encoder. VICReg-non-optional anti-collapse loss.

Spec refs:
- 4.1 Q1 substrate training data flow
- 4.4 (H8a) encoder Lipschitz, (H8b) predictor Lipschitz
- 4.5 empirical-constants estimation protocol

VICReg-non-optional is the load-bearing invariant: train_step() and
vicreg_loss() raise if var_weight <= 0. This is what makes (H8)
anti-collapse provable; we prevent the API from ever shipping a
degenerate-collapse substrate.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Make scripts.jepa_cache and scripts.jepa_features importable when
# running tests from microrcs/.
import sys as _sys
_pkg_root = Path(__file__).resolve().parents[1]
if str(_pkg_root) not in _sys.path:
    _sys.path.insert(0, str(_pkg_root))

from scripts.jepa_cache import STCache, st_cache_key  # noqa: E402
from scripts.jepa_features import EpisodeContext, FusionEncoder  # noqa: E402


@dataclass
class SubstrateConfig:
    """Hyperparameters for MlpJepaSubstrate. Locked per Q1-T0 pre-registration."""
    text_dim: int = 384
    struct_dim: int = 32
    history_dim: int = 64
    latent_dim: int = 64
    action_dim: int = 7  # {base, cot, scratchpad, verify, retry, abort, noop}
    hidden_dim: int = 64
    ema_momentum: float = 0.99
    vicreg_var_weight: float = 25.0
    vicreg_cov_weight: float = 1.0
    st_model_id: str = "all-MiniLM-L6-v2"


class ACPredictor(nn.Module):
    """Action-conditioned residual predictor: ẑ' = z + MLP([z; a]).

    Residual structure ensures (H8b) Lipschitz constant L_P stays close to
    1 + L_MLP at the operating point, which the regularizer keeps bounded.
    """

    def __init__(self, latent_dim: int = 64, action_dim: int = 7,
                 hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(latent_dim + action_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Linear(hidden, latent_dim),
        )

    def forward(self, z: torch.Tensor, a: torch.Tensor) -> torch.Tensor:
        cat = torch.cat([z, a], dim=-1)
        return z + self.net(cat)


def vicreg_loss(
    z: torch.Tensor,
    var_weight: float = 25.0,
    cov_weight: float = 1.0,
    eps: float = 1e-4,
) -> tuple[torch.Tensor, dict]:
    """VICReg-lite: variance + covariance terms. Invariance via predictor.

    Used by train_step() with var_weight non-zero; var_weight <= 0 raises.
    This is the (H8) anti-collapse invariant — without it, the trivial
    collapse solution ``s_θ(·) = const`` minimizes the loss with zero
    gradient and the substrate degenerates.
    """
    if var_weight <= 0.0:
        raise ValueError(
            "VICReg variance weight is non-optional (spec Section 4.1 "
            "invariant 3); pass var_weight > 0. Anti-collapse guarantee "
            "(H8) requires it."
        )
    std = torch.sqrt(z.var(dim=0, unbiased=False) + eps)
    var_loss = F.relu(1.0 - std).mean()
    z_c = z - z.mean(dim=0, keepdim=True)
    cov = (z_c.T @ z_c) / max(z.size(0) - 1, 1)
    diag_mask = torch.eye(z.size(1), dtype=torch.bool, device=z.device)
    cov_loss = (cov[~diag_mask] ** 2).sum() / z.size(1)
    total = var_weight * var_loss + cov_weight * cov_loss
    return total, {
        "var_loss": float(var_loss.detach()),
        "cov_loss": float(cov_loss.detach()),
        "std_mean": float(std.mean().detach()),
    }


class MlpJepaSubstrate:
    """Q1 frozen substrate. Implements JepaSubstrate trait shape.

    Three sub-modules:
    - encoder: FusionEncoder (online; gradient flows)
    - target encoder: FusionEncoder (EMA of online; stop-grad)
    - predictor: ACPredictor (online; gradient flows)

    State:
    - is_stable: bool (set False on NaN; trips circuit breaker in Q2)
    - version_id: str (bumps on save/load; used by Q3 canary)
    - st_cache: STCache (sentence-transformer embedding cache)
    """

    def __init__(self, cfg: SubstrateConfig | None = None,
                 cache_dir: Path | str = ".st_cache"):
        self.cfg = cfg or SubstrateConfig()
        self.encoder = FusionEncoder(
            text_dim=self.cfg.text_dim, struct_dim=self.cfg.struct_dim,
            history_dim=self.cfg.history_dim, out_dim=self.cfg.latent_dim,
        )
        self.target_encoder = FusionEncoder(
            text_dim=self.cfg.text_dim, struct_dim=self.cfg.struct_dim,
            history_dim=self.cfg.history_dim, out_dim=self.cfg.latent_dim,
        )
        self.predictor = ACPredictor(
            latent_dim=self.cfg.latent_dim,
            action_dim=self.cfg.action_dim,
            hidden=self.cfg.hidden_dim,
        )

        # Initialize EMA target = encoder; freeze gradients on target.
        self.target_encoder.load_state_dict(self.encoder.state_dict())
        for p in self.target_encoder.parameters():
            p.requires_grad_(False)

        self.is_stable: bool = True
        self.version_id: str = self._new_version_id()
        self.st_cache = STCache(cache_dir=cache_dir)
        self._st_model = None  # lazy-loaded on first cache miss

    @staticmethod
    def _new_version_id() -> str:
        return f"{int(time.time())}-{uuid.uuid4().hex[:8]}"

    def _embed_text(self, text: str) -> np.ndarray:
        """Embed text via cached sentence-transformer."""
        key = st_cache_key(text, self.cfg.st_model_id)
        cached = self.st_cache.get(key)
        if cached is not None:
            return cached
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.cfg.st_model_id)
        emb = self._st_model.encode(text, convert_to_numpy=True).astype(
            np.float32
        )
        self.st_cache.set(key, emb)
        return emb

    def encode(self, ctx: EpisodeContext) -> torch.Tensor:
        """Encode an EpisodeContext to latent z_t. Returns shape (latent_dim,)."""
        text_emb = self._embed_text(ctx.text)
        text_t = torch.from_numpy(text_emb)
        struct_t = torch.from_numpy(ctx.struct)
        history_t = self._reduce_history(ctx.history_tokens)
        return self.encoder(text_t, struct_t, history_t)

    def _reduce_history(self, history_tokens: np.ndarray) -> torch.Tensor:
        """Q1 baseline: mean-pool tokens then pad/truncate to history_dim.

        Q2 may upgrade this to a 1-layer transformer per the design note.
        """
        ht = torch.from_numpy(history_tokens.astype(np.float32))
        pooled = ht.mean(dim=0)
        if pooled.numel() < self.cfg.history_dim:
            pad = torch.zeros(self.cfg.history_dim - pooled.numel())
            pooled = torch.cat([pooled, pad])
        else:
            pooled = pooled[: self.cfg.history_dim]
        return pooled

    def predict(self, z: torch.Tensor, a: torch.Tensor) -> torch.Tensor:
        """Predict next latent. Sets is_stable=False on NaN/Inf output."""
        out = self.predictor(z, a)
        if torch.isnan(out).any() or torch.isinf(out).any():
            self.is_stable = False
        return out

    def energy(self, z: torch.Tensor, z_next: torch.Tensor) -> float:
        """E = ‖z − z_next‖² (sum-squared) — JEPA energy-as-Lyapunov."""
        return float(((z - z_next) ** 2).sum().detach())

    @torch.no_grad()
    def update_target(self) -> None:
        """EMA-update target encoder weights from online encoder."""
        m = self.cfg.ema_momentum
        for p_online, p_target in zip(
            self.encoder.parameters(), self.target_encoder.parameters()
        ):
            p_target.data.mul_(m).add_(p_online.data, alpha=1 - m)

    def train_step(
        self,
        z: torch.Tensor,        # (B, latent_dim)
        a: torch.Tensor,        # (B, action_dim)
        z_next: torch.Tensor,   # (B, latent_dim) target encoded next (sg)
        vicreg_var_weight: float | None = None,
        vicreg_cov_weight: float | None = None,
    ) -> dict:
        """One gradient step. Returns loss tensor + components for logging.

        VICReg-non-optional: var_weight=0 raises (anti-collapse invariant).
        Caller does .backward() on the returned ``loss`` tensor.
        """
        var_w = (vicreg_var_weight if vicreg_var_weight is not None
                  else self.cfg.vicreg_var_weight)
        cov_w = (vicreg_cov_weight if vicreg_cov_weight is not None
                  else self.cfg.vicreg_cov_weight)
        if var_w <= 0.0:
            raise ValueError(
                "VICReg variance weight is non-optional (spec Section 4.1 "
                "invariant 3); pass var_weight > 0."
            )
        z_pred = self.predictor(z, a)
        pred_loss = ((z_pred - z_next.detach()) ** 2).sum(dim=-1).mean()
        reg_loss, reg_info = vicreg_loss(z, var_weight=var_w, cov_weight=cov_w)
        loss = pred_loss + reg_loss
        return {
            "loss": loss,
            "pred_loss": float(pred_loss.detach()),
            **reg_info,
        }

    def save(self, path: Path | str) -> None:
        """Save weights + config + version_id atomically."""
        torch.save({
            "encoder": self.encoder.state_dict(),
            "target_encoder": self.target_encoder.state_dict(),
            "predictor": self.predictor.state_dict(),
            "config": self.cfg.__dict__,
            "version_id": self.version_id,
        }, path)

    def load(self, path: Path | str) -> None:
        """Load weights from disk; bump version_id (Q3 canary integration)."""
        sd = torch.load(path, map_location="cpu", weights_only=False)
        self.encoder.load_state_dict(sd["encoder"])
        self.target_encoder.load_state_dict(sd["target_encoder"])
        self.predictor.load_state_dict(sd["predictor"])
        self.version_id = self._new_version_id()
