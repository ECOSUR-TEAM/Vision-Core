# ReID slice

`domain/` defines the identity contracts, `application/` exposes embedding and
resolution use cases through immutable DTOs, and `infrastructure/` contains the
torchvision embedding extractor and the in-memory gallery.

`person_id` is a local identity resolved from embeddings, not a real person's
name. Do not mix embeddings from different models in one session.

## Documentation

- [Pipeline data flow](../../../../docs/diagrams.md#flujo-de-datos)
- [Configuration: ReID variables](../../../../docs/configuration.md#reid)
- [Glossary: person_id, embedding, gallery and TTL](../../../../docs/glossary.md)
- [Runbook: model or inference error](../../../../docs/runbooks/03-modelo-no-encontrado-o-error-de-inferencia.md)
- [ADR 0003: multi-camera proposal](../../../../docs/adr/0003-modelo-ejecucion-multi-camara.md)
