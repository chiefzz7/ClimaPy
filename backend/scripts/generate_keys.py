"""Gerador local de chaves Fernet e VAPID P-256 para o ClimaPy.

Uso:
    python backend/scripts/generate_keys.py           # Apenas exibe no stdout
    python backend/scripts/generate_keys.py --write   # Preenche chaves vazias no .env
"""

from __future__ import annotations

import argparse
import base64
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"


@dataclass(frozen=True, slots=True)
class GeneratedKeys:
    """Conjunto de chaves locais geradas para criptografia e Web Push VAPID."""

    data_encryption_key: str
    vapid_public_key: str
    vapid_private_key: str


def _b64url_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_local_keys() -> GeneratedKeys:
    """Gera uma chave Fernet e um par de chaves ECDSA P-256 compatível com VAPID."""
    data_key = Fernet.generate_key().decode("ascii")

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    return GeneratedKeys(
        data_encryption_key=data_key,
        vapid_public_key=_b64url_nopad(public_bytes),
        vapid_private_key=_b64url_nopad(private_bytes),
    )


def write_keys_to_env(
    env_path: Path,
    example_path: Path,
    *,
    force: bool = False,
) -> list[str]:
    """Cria ou atualiza o arquivo .env preservando valores existentes, salvo com force=True."""
    keys = generate_local_keys()
    target_values = {
        "DATA_ENCRYPTION_KEY": keys.data_encryption_key,
        "VAPID_PUBLIC_KEY": keys.vapid_public_key,
        "VAPID_PRIVATE_KEY": keys.vapid_private_key,
    }

    if env_path.exists():
        raw_lines = env_path.read_text(encoding="utf-8").splitlines()
    elif example_path.exists():
        raw_lines = example_path.read_text(encoding="utf-8").splitlines()
    else:
        raw_lines = [f"{k}=" for k in target_values]

    updated_keys: list[str] = []
    seen_keys: set[str] = set()
    new_lines: list[str] = []

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue

        key_name, current_val = line.split("=", 1)
        key_name_clean = key_name.strip()
        if key_name_clean in target_values:
            seen_keys.add(key_name_clean)
            if force or not current_val.strip():
                new_lines.append(f"{key_name_clean}={target_values[key_name_clean]}")
                updated_keys.append(key_name_clean)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key_name, val in target_values.items():
        if key_name not in seen_keys:
            new_lines.append(f"{key_name}={val}")
            updated_keys.append(key_name)

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)
    return updated_keys


def main() -> int:
    """Ponto de entrada CLI."""
    parser = argparse.ArgumentParser(description="Gerador local de chaves Fernet e VAPID.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Escreve as chaves geradas no arquivo .env (apenas se estiverem vazias).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve chaves já preenchidas quando usado com --write.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="Caminho alternativo para o arquivo .env.",
    )
    args = parser.parse_args()

    if args.write:
        updated = write_keys_to_env(
            env_path=args.env_file,
            example_path=DEFAULT_EXAMPLE_PATH,
            force=args.force,
        )
        if updated:
            joined = ", ".join(updated)
            print(f"Chaves gravadas em {args.env_file} (permissão 0600): {joined}")
        else:
            print(f"Nenhuma chave alterada em {args.env_file}; use --force para rotacionar.")
        return 0

    keys = generate_local_keys()
    print(f"DATA_ENCRYPTION_KEY={keys.data_encryption_key}")
    print(f"VAPID_PUBLIC_KEY={keys.vapid_public_key}")
    print(f"VAPID_PRIVATE_KEY={keys.vapid_private_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
