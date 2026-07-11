"""``InMemoryLedger`` — the fast, ephemeral ledger double (docs/55 §2; parity-critical).

Implemented as a ``Ledger`` subclass over a per-instance temp directory that is removed on
``close()``/GC. This is the strongest anti-drift guarantee (RISKS R3): the double IS the
real IF-1 implementation, so append/read/replay/snapshot/restore have identical signatures
AND semantics — a test can never validate a fiction. "In-memory" = ephemeral + auto-managed
(no persistent K: state), not a reimplementation of the hash-chain fold.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable

from charterhouse.ledger import Ledger


class InMemoryLedger(Ledger):
    """A ``Ledger`` over a throwaway temp dir. Same public surface as ``Ledger`` (docs/40
    §2) by inheritance; nothing durable survives the process."""

    def __init__(self, *, new_id: Callable[[], str] | None = None) -> None:
        self._tmp = tempfile.mkdtemp(prefix="charterhouse-inmem-ledger-")
        super().__init__(self._tmp, backup_dir=self._tmp + "-backups", new_id=new_id)

    def close(self) -> None:
        """Remove the ephemeral storage. Idempotent."""
        shutil.rmtree(self._tmp, ignore_errors=True)
        shutil.rmtree(self._tmp + "-backups", ignore_errors=True)

    def __del__(self) -> None:  # best-effort cleanup
        try:
            self.close()
        except Exception:
            pass
