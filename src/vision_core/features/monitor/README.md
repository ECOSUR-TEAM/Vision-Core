# Monitor slice

The monitor feature owns telemetry state, frame rendering, and its HTTP
transport. Its application layer exposes state publication and read use cases
through DTOs; the composition root injects the pipeline callbacks and state.

The feature deliberately has no domain ports: the monitor consumes already
resolved pipeline data through application use cases, so no additional domain
contract is required.
