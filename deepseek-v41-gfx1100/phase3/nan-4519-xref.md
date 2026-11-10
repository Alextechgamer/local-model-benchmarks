> [!NOTE]
> **AI-assisted report.** Prepared with Claude (Anthropic, Claude Opus 5.5 in Claude Code) on my machine and reviewed by me.

One caveat for a gfx1100 package, from a self-built `strata-dsv41` 0.1.58 on an RX 7900 XT under Windows: with experts
in VRAM (the default placement), a long fresh prompt can end in "NaN reached the router". With ISTA's stock
IQ1_M files it happened in 1 of 3 fresh 19,900-token prompts, so it is not only modified files. After a stop the server can keep failing until it is restarted
(seen in 1 of 2 cases). `--vram-experts 0` avoids it at about 15% of decode speed. The details and reproducers are in #5259, which
reports the same error on RTX 40 cards: <link to the #5259 comment>.
