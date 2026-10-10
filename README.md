# oi-harness

Runtime agent untuk Oi — harness LangGraph yang menjalankan agent, plus sistem plugin,
tool bawaan, paket skill, backend workspace, dan integrasi ACP.

Bagian dari [Oi](https://github.com/akankofik-dev/Oi); dipakai via git pin, tidak dipublikasikan di PyPI.

## Install

```bash
pip install "git+https://github.com/akankofik-dev/oi-harness.git@v1.0.1"
```

Dari checkout Oi, paket ini dideklarasikan di `[tool.uv.sources]`, jadi `uv sync` menyelesaikannya.

## Isi

| Modul | Fungsi |
|---|---|
| `oi_harness.plugins` | Penemuan dan pemuatan plugin |
| `oi_harness.backends` | Backend workspace: lokal, Docker, remote |
| `oi_harness.registry` | Registry provider dan tool |
| `oi_harness.security` | Aturan guard tool dan penanganan PII |
| `oi_harness.teams` | Tim multi-agent dan sub-agent |

## Extras

Tersedia 14 extras, terutama `[all]` yang menarik Docker, Langfuse, object storage
OSS/COS, backend remote, dan provider web-search. Oi menginstall `oi-harness[all]`.

## Lisensi

MIT — lihat [LICENSE](LICENSE).
