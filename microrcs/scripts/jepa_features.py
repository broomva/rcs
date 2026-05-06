"""3-source feature pipeline for Q1 substrate (Q1-T4).

Maps an EpisodeContext (text + struct + history) → 64-d latent z_t.
- text: 384-d frozen sentence-transformer embedding (cached via jepa_cache)
- struct: 32-d normalized scalar features (cost, tokens, latency, step_idx)
- history: last-K events tokenized → 1-layer transformer → 64-d

Fused via concat → 480-d → linear projection → 64-d.

Spec ref: 4.1 Q1 substrate training data flow.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn

# Token vocab for history featurization. Order is fixed at first sight; do
# not reorder. Maps tool names + an out-of-vocab token + a pad token.
_HISTORY_TOOL_VOCAB: tuple[str, ...] = (
    "<pad>", "<oov>", "bash", "submit", "<no-decide>",
)


@dataclass
class EpisodeContext:
    """Input to the encoder. Three sources, one struct."""
    text: str                      # Concatenated message + tool I/O
    struct: np.ndarray             # 32-d
    history_tokens: np.ndarray     # (max_history, token_dim)


class StructFeatures:
    """Hand-engineered scalar feature extractor → 32-d normalized vector.

    Layout (deterministic; do not reorder):
      [0]  cost_norm           (cost / max_cost_usd, capped at 1.0)
      [1]  steps_norm          (steps / max_steps)
      [2]  latency_norm        (log1p(latency_ms) / 10)
      [3]  input_tokens_norm   (log1p(input_tokens) / 10)
      [4]  output_tokens_norm  (log1p(output_tokens) / 10)
      [5]  step_idx_norm       (step_idx / max_step_idx)
      [6-31] reserved (zeros) — leaves room for future additions without
            breaking encoder expected dim
    """

    def __init__(self, max_cost_usd: float = 0.50, max_steps: int = 20,
                 max_step_idx: int = 100):
        self.max_cost_usd = max_cost_usd
        self.max_steps = max_steps
        self.max_step_idx = max_step_idx

    def encode(self, rec: dict) -> np.ndarray:
        feat = np.zeros(32, dtype=np.float32)
        feat[0] = min(rec.get("cost", 0.0) / max(self.max_cost_usd, 1e-9), 1.0)
        feat[1] = min(rec.get("steps", rec.get("n_steps", 0))
                       / max(self.max_steps, 1), 1.0)
        feat[2] = math.log1p(max(rec.get("latency_ms", 0), 0)) / 10.0
        feat[3] = math.log1p(max(rec.get("input_tokens", 0), 0)) / 10.0
        feat[4] = math.log1p(max(rec.get("output_tokens", 0), 0)) / 10.0
        feat[5] = min(rec.get("step", rec.get("step_idx", 0))
                       / max(self.max_step_idx, 1), 1.0)
        # 6-31 reserved (zeros)
        return feat


def extract_struct(rec: dict) -> np.ndarray:
    """Module-level convenience wrapper. Uses default StructFeatures config."""
    return StructFeatures().encode(rec)


class HistoryFeatures:
    """Tokenizer for event history. Emits (max_history, token_dim) array.

    Each event becomes a token_dim-d vector concatenating:
      [0:N] one-hot tool_vocab
      [N]   is_error (0/1)
      [N+1] obs_len_log (log1p(obs_len)/10)
    """

    def __init__(self, max_history: int = 5,
                 vocab: tuple[str, ...] = _HISTORY_TOOL_VOCAB):
        self.max_history = max_history
        self.vocab = vocab
        self.token_dim = len(vocab) + 2  # one-hot + is_error + obs_len_log
        self._pad_token = self._build_token({"tool": "<pad>"})

    def _build_token(self, ev: dict) -> np.ndarray:
        token = np.zeros(self.token_dim, dtype=np.float32)
        tool = ev.get("tool", "<oov>")
        if tool not in self.vocab:
            tool = "<oov>"
        token[self.vocab.index(tool)] = 1.0
        token[len(self.vocab)] = 1.0 if ev.get("is_error") else 0.0
        token[len(self.vocab) + 1] = math.log1p(
            max(ev.get("obs_len", 0), 0)
        ) / 10.0
        return token

    def tokenize(self, events: list[dict]) -> np.ndarray:
        """Tokenize a list of events. Last K events; pad-tail if shorter."""
        recent = events[-self.max_history:]
        tokens = [self._build_token(e) for e in recent]
        # Pad-tail to max_history (real events first, pads after)
        while len(tokens) < self.max_history:
            tokens.append(self._pad_token)
        return np.stack(tokens, axis=0)


def extract_history_tokens(events: list[dict], max_history: int = 5,
                            token_dim: int = 8) -> np.ndarray:
    """Module-level convenience. Uses default HistoryFeatures config."""
    h = HistoryFeatures(max_history=max_history)
    if h.token_dim != token_dim:
        # Caller asked for a different token_dim; fall back to zeros.
        return np.zeros((max_history, token_dim), dtype=np.float32)
    return h.tokenize(events)


class FusionEncoder(nn.Module):
    """Fuse text + struct + history → 64-d latent z_t.

    text_dim=384 (sentence-transformer), struct_dim=32, history_dim=64
    (post-transformer). Concatenate → 480-d → 2-layer MLP → 64-d.
    """

    def __init__(self, text_dim: int = 384, struct_dim: int = 32,
                 history_dim: int = 64, out_dim: int = 64):
        super().__init__()
        self.fusion = nn.Sequential(
            nn.Linear(text_dim + struct_dim + history_dim, 128),
            nn.GELU(),
            nn.Linear(128, out_dim),
        )

    def forward(self, text: torch.Tensor, struct: torch.Tensor,
                 history: torch.Tensor) -> torch.Tensor:
        cat = torch.cat([text, struct, history], dim=-1)
        return self.fusion(cat)
