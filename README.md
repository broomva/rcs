# Recursive Controlled Systems (RCS)

A self-similar control-theoretic formalization for autonomous AI agents.

## Abstract

We introduce the **Recursive Controlled System** (RCS), a 7-tuple
$\Sigma = (\mathcal{X}, \mathcal{Y}, \mathcal{U}, f, h, S, \Pi)$ whose
controller $\Pi$ is itself an RCS at the next hierarchical level. This
produces a self-similar hierarchy where the same state-space structure —
state, observation, control, dynamics, safety shield, controller — applies at
every level, from external plant control through internal homeostasis through
meta-optimization through governance.

We define the **homeostatic drive** as a Lyapunov candidate that simultaneously
serves as stability certificate, reward signal, and free energy bound —
unifying control theory, reinforcement learning, and active inference. Extending
the stability budget of Eslami & Yu (2026) to the recursive case, we derive
conditions under which the composite multi-level system is exponentially stable.

The self-referential loop is closed      
                                                                                             
  Agent reads CLAUDE.md/AGENTS.md (Π₃)                                                     
    → understands it IS the plant being regulated                                            
    → operates under stability constraint λ₃ > 0                                             
    → emits events → fold → HomeostaticState → rules                                         
    → discovers patterns → conversation log (h₃)                                             
    → if recurring → crystallizes into AGENTS.md (f₃)                                        
    → future agents read the updated rules                                                   
    → THE SYSTEM HAS IMPROVED ITSELF                                                         
    → and it knows WHY this works (Theorem 1, Proposition 4)

## Paper Series

| # | Title | Status | Target |
|---|-------|--------|--------|
| P0 | RCS Foundations | Drafting | Workshop, Dec 2026 |
| P1 | Homeostatic Stability | Planned | CDC/L4DC, May 2027 |
| P2 | EGRI as Meta-Controller | Planned | ICML/AAMAS, May 2027 |
| P3 | Self-Referential Observers | Planned | AAAI, Sep 2027 |
| P4 | Fleet Cooperative Resilience | Planned | IEEE TAI, Mar 2028 |

## Building the LaTeX

Requires [tectonic](https://tectonic-typesetting.github.io/):

```bash
brew install tectonic
cd latex
tectonic rcs-definitions.tex
```

## Structure

```
rcs/
├── papers/           # Paper drafts (one folder per paper)
│   ├── p0-foundations/
│   ├── p1-stability/
│   ├── p2-egri/
│   ├── p3-observers/
│   └── p4-fleet/
├── latex/            # Formal definitions, proofs, shared macros
├── specs/            # Design specifications
├── references/       # Reading notes (PDFs gitignored)
└── docs/             # Working documents, mapping tables
```

## Key References

- Eslami & Yu (2026). "A Control-Theoretic Foundation for Agentic Systems." arXiv:2603.10779
- Keramati & Gutkin (2014). "Homeostatic reinforcement learning." eLife.
- Ashby (1952). *Design for a Brain.* Chapman & Hall.
- Beer (1972). *Brain of the Firm.* Allen Lane.
- Quijano et al. (2017). "Population Games in Distributed Control." IEEE CSM.
- Chacon-Chamorro et al. (2025). "Cooperative Resilience in AI MAS." IEEE TAI.

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — cite as:

> Escobar-Valbuena, C. D. (2026). Recursive Controlled Systems: A Self-Similar
> Control-Theoretic Foundation for Autonomous AI Agents. Working draft.
