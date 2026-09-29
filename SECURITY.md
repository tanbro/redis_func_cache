# Security Policy

## Supported Versions

Security fixes are applied to the latest release only. Older versions do not receive security updates; please upgrade.

| Version   | Supported          |
| --------- | ------------------ |
| 1.0.x     | :white_check_mark: |
| < 1.0     | :x:                |

## Reporting a Vulnerability

Please report vulnerabilities privately via [GitHub's private vulnerability reporting](https://github.com/tanbro/redis_func_cache/security/advisories/new) rather than opening a public issue.

You can expect an initial response within 7 days, and status updates at least every 7 days until the report is resolved.

If a report is accepted, a fix is released as soon as practical, followed by a GitHub Security Advisory (CVE where applicable). If it is declined, you will receive an explanation of the reasoning.

### Scope notes

- **Deserialization:**

  cached values are serialized with the configured serializer.
  `pickle`, `dill` and `cloudpickle` can execute arbitrary code during deserialization — this is documented behavior, not a vulnerability in itself (see [docs/usage/configuration.md](docs/usage/configuration.md)).
  A report only qualifies as a vulnerability if the library deserializes data the user did not opt in to deserialize that way.

- **Redis exposure:**

  the library relies on the connection security of the Redis deployment (TLS, ACLs, network isolation) and does not encrypt cache content itself.
  Encrypting cached values via a custom handler/serializer is the supported approach.
