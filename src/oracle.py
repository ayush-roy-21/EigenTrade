"""
Oracle database helpers for EigenTrades ingestion and analytics.

Environment variables used:
- ORACLE_USER
- ORACLE_PASSWORD
- ORACLE_DSN (example: localhost:1521/orclpdb1)
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any, Sequence

logger = logging.getLogger("oracle")


def _import_oracle_driver() -> Any:
	"""Import oracledb first, then fall back to cx_Oracle."""
	try:
		import oracledb  # type: ignore

		return oracledb
	except Exception:
		import cx_Oracle  # type: ignore

		return cx_Oracle


ORACLE_DRIVER = _import_oracle_driver()


@dataclass(frozen=True)
class OracleConfig:
	user: str
	password: str
	dsn: str

	@classmethod
	def from_env(cls) -> "OracleConfig":
		user = os.getenv("ORACLE_USER", "")
		password = os.getenv("ORACLE_PASSWORD", "")
		dsn = os.getenv("ORACLE_DSN", "")

		missing = [
			key
			for key, value in {
				"ORACLE_USER": user,
				"ORACLE_PASSWORD": password,
				"ORACLE_DSN": dsn,
			}.items()
			if not value
		]
		if missing:
			raise ValueError(f"Missing Oracle environment variables: {', '.join(missing)}")

		return cls(user=user, password=password, dsn=dsn)


class OracleClient:
	"""Lightweight Oracle client with transaction-safe helpers."""

	def __init__(self, config: OracleConfig):
		self.config = config

	def connect(self) -> Any:
		return ORACLE_DRIVER.connect(
			user=self.config.user,
			password=self.config.password,
			dsn=self.config.dsn,
		)

	def execute_many(self, statement: str, rows: Sequence[Any], batch_size: int = 1000) -> int:
		"""
		Execute a parameterized statement in batches.
		Returns the number of rows attempted.
		"""
		if not rows:
			return 0

		attempted = 0
		connection = self.connect()
		try:
			cursor = connection.cursor()
			for start in range(0, len(rows), batch_size):
				chunk = rows[start : start + batch_size]
				cursor.executemany(statement, chunk)
				attempted += len(chunk)
			connection.commit()
			return attempted
		except Exception:
			connection.rollback()
			logger.exception("Oracle execute_many failed")
			raise
		finally:
			connection.close()

	def execute(self, statement: str, params: dict[str, Any] | None = None) -> None:
		"""Execute one statement inside a transaction."""
		connection = self.connect()
		try:
			cursor = connection.cursor()
			cursor.execute(statement, params or {})
			connection.commit()
		except Exception:
			connection.rollback()
			logger.exception("Oracle execute failed")
			raise
		finally:
			connection.close()

	def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[tuple[Any, ...]]:
		"""Run a query and return all rows."""
		connection = self.connect()
		try:
			cursor = connection.cursor()
			cursor.execute(query, params or {})
			return cursor.fetchall()
		finally:
			connection.close()


def create_client_from_env() -> OracleClient:
	return OracleClient(OracleConfig.from_env())
