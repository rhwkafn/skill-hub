"""
File Encryption - Encrypt and decrypt files using AES-256-GCM.

Supports:
- Password-based key derivation (PBKDF2)
- Single file encryption/decryption
- Recursive directory encryption/decryption
- Authenticated encryption (integrity verification)
"""

import os
import json
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass

# Use cryptography library if available, fall back to a pure-python approach
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SALT_SIZE = 32
NONCE_SIZE = 12
KEY_LENGTH = 32  # AES-256
PBKDF2_ITERATIONS = 600_000
ENCRYPTED_EXTENSION = ".enc"
MAGIC_HEADER = b"ENC1"  # 4-byte file format identifier


@dataclass
class EncryptionMetadata:
    """Metadata stored alongside encrypted data."""
    salt: bytes
    nonce: bytes
    iterations: int = PBKDF2_ITERATIONS


def derive_key(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """Derive an AES-256 key from a password using PBKDF2-SHA256.

    Args:
        password: The user's password.
        salt: Random salt bytes.
        iterations: Number of PBKDF2 iterations.

    Returns:
        32-byte derived key.
    """
    if HAS_CRYPTOGRAPHY:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))
    else:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=KEY_LENGTH,
        )


def _aes_encrypt(key: bytes, nonce: bytes, plaintext: bytes, associated_data: Optional[bytes] = None) -> bytes:
    """Encrypt plaintext using AES-256-GCM."""
    if HAS_CRYPTOGRAPHY:
        aesgcm = AESGCM(key)
        return aesgcm.encrypt(nonce, plaintext, associated_data)
    else:
        # Fallback: use XOR with AES-CTR simulation (not production-grade)
        # In real use, the 'cryptography' package should be installed.
        raise RuntimeError(
            "The 'cryptography' package is required for encryption. "
            "Install it with: pip install cryptography"
        )


def _aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: Optional[bytes] = None) -> bytes:
    """Decrypt ciphertext using AES-256-GCM."""
    if HAS_CRYPTOGRAPHY:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data)
    else:
        raise RuntimeError(
            "The 'cryptography' package is required for decryption. "
            "Install it with: pip install cryptography"
        )


# ---------------------------------------------------------------------------
# File-level operations
# ---------------------------------------------------------------------------

def encrypt_file(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    password: str = "",
    remove_original: bool = False,
) -> Path:
    """Encrypt a single file using AES-256-GCM with a password.

    File format: [MAGIC(4)][SALT(32)][NONCE(12)][CIPHERTEXT+TAG]

    Args:
        input_path: Path to the file to encrypt.
        output_path: Path for the encrypted file. Defaults to input_path + '.enc'.
        password: Password for key derivation.
        remove_original: If True, securely delete the original file after encryption.

    Returns:
        Path to the encrypted file.

    Raises:
        FileNotFoundError: If input_path does not exist.
        ValueError: If password is empty.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not password:
        raise ValueError("Password must not be empty")

    if output_path is None:
        output_path = input_path.with_suffix(input_path.suffix + ENCRYPTED_EXTENSION)
    output_path = Path(output_path)

    salt = secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)
    key = derive_key(password, salt)

    with open(input_path, "rb") as f:
        plaintext = f.read()

    # Associated data: original filename (for verification)
    aad = input_path.name.encode("utf-8")
    ciphertext = _aes_encrypt(key, nonce, plaintext, aad)

    with open(output_path, "wb") as f:
        f.write(MAGIC_HEADER)
        f.write(salt)
        f.write(nonce)
        f.write(len(aad).to_bytes(2, "big"))
        f.write(aad)
        f.write(ciphertext)

    if remove_original:
        _secure_delete(input_path)

    return output_path


def decrypt_file(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    password: str = "",
) -> Path:
    """Decrypt a file encrypted with encrypt_file().

    Args:
        input_path: Path to the encrypted file.
        output_path: Path for the decrypted file. Defaults to removing '.enc' extension.
        password: Password used during encryption.

    Returns:
        Path to the decrypted file.

    Raises:
        FileNotFoundError: If input_path does not exist.
        ValueError: If the file format is invalid or password is wrong.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Encrypted file not found: {input_path}")

    with open(input_path, "rb") as f:
        magic = f.read(len(MAGIC_HEADER))
        if magic != MAGIC_HEADER:
            raise ValueError("Not a valid encrypted file (bad magic header)")

        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        aad_len = int.from_bytes(f.read(2), "big")
        aad = f.read(aad_len)
        ciphertext = f.read()

    key = derive_key(password, salt)

    try:
        plaintext = _aes_decrypt(key, nonce, ciphertext, aad)
    except Exception:
        raise ValueError("Decryption failed: wrong password or corrupted file")

    if output_path is None:
        # Strip .enc extension
        original_name = input_path.stem
        if input_path.suffix == ENCRYPTED_EXTENSION:
            output_path = input_path.parent / original_name
        else:
            output_path = input_path.with_suffix(".decrypted")
    output_path = Path(output_path)

    with open(output_path, "wb") as f:
        f.write(plaintext)

    return output_path


# ---------------------------------------------------------------------------
# Directory-level operations
# ---------------------------------------------------------------------------

def encrypt_directory(
    directory: Union[str, Path],
    password: str,
    recursive: bool = True,
    remove_originals: bool = False,
    exclude_extensions: Optional[list] = None,
) -> list:
    """Encrypt all files in a directory.

    Args:
        directory: Path to the directory.
        password: Password for encryption.
        recursive: If True, encrypt files in subdirectories too.
        remove_originals: If True, delete original files after encryption.
        exclude_extensions: List of file extensions to skip (e.g., ['.enc', '.py']).

    Returns:
        List of (original_path, encrypted_path) tuples.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    exclude = set(exclude_extensions or [ENCRYPTED_EXTENSION])
    results = []

    pattern = "**/*" if recursive else "*"
    for file_path in sorted(directory.glob(pattern)):
        if not file_path.is_file():
            continue
        if file_path.suffix in exclude:
            continue

        enc_path = encrypt_file(
            file_path,
            password=password,
            remove_original=remove_originals,
        )
        results.append((file_path, enc_path))

    return results


def decrypt_directory(
    directory: Union[str, Path],
    password: str,
    recursive: bool = True,
) -> list:
    """Decrypt all .enc files in a directory.

    Args:
        directory: Path to the directory.
        password: Password for decryption.
        recursive: If True, decrypt files in subdirectories too.

    Returns:
        List of (encrypted_path, decrypted_path) tuples.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    results = []
    pattern = "**/*" if recursive else "*"

    for file_path in sorted(directory.glob(pattern)):
        if not file_path.is_file():
            continue
        if file_path.suffix != ENCRYPTED_EXTENSION:
            continue

        dec_path = decrypt_file(file_path, password=password)
        results.append((file_path, dec_path))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _secure_delete(file_path: Path) -> None:
    """Overwrite file content before deletion to prevent recovery."""
    size = file_path.stat().st_size
    with open(file_path, "wb") as f:
        f.write(secrets.token_bytes(size))
        f.flush()
        os.fsync(f.fileno())
    file_path.unlink()


def generate_password(length: int = 20) -> str:
    """Generate a cryptographically secure random password.

    Args:
        length: Desired password length (minimum 12).

    Returns:
        A random password string.
    """
    length = max(length, 12)
    return secrets.token_urlsafe(length)[:length]


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def main():
    """Command-line interface for file encryption/decryption."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Encrypt or decrypt files using AES-256-GCM"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Encrypt command
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt a file or directory")
    enc_parser.add_argument("path", help="File or directory to encrypt")
    enc_parser.add_argument("-o", "--output", help="Output path (file only)")
    enc_parser.add_argument("-p", "--password", help="Password (will prompt if omitted)")
    enc_parser.add_argument("--remove", action="store_true", help="Remove original files")
    enc_parser.add_argument("--recursive", action="store_true", default=True,
                            help="Recurse into subdirectories")

    # Decrypt command
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt a file or directory")
    dec_parser.add_argument("path", help="File or directory to decrypt")
    dec_parser.add_argument("-o", "--output", help="Output path (file only)")
    dec_parser.add_argument("-p", "--password", help="Password (will prompt if omitted)")

    # Generate password command
    subparsers.add_parser("generate-password", help="Generate a random secure password")

    args = parser.parse_args()

    if args.command == "generate-password":
        print(generate_password())
        return

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Enter password: ")

    target = Path(args.path)

    if args.command == "encrypt":
        if target.is_dir():
            results = encrypt_directory(
                target,
                password=password,
                recursive=args.recursive,
                remove_originals=args.remove,
            )
            print(f"Encrypted {len(results)} files:")
            for orig, enc in results:
                print(f"  {orig} -> {enc}")
        else:
            out = encrypt_file(
                target,
                output_path=args.output,
                password=password,
                remove_original=args.remove,
            )
            print(f"Encrypted: {target} -> {out}")

    elif args.command == "decrypt":
        if target.is_dir():
            results = decrypt_directory(target, password=password)
            print(f"Decrypted {len(results)} files:")
            for enc, dec in results:
                print(f"  {enc} -> {dec}")
        else:
            out = decrypt_file(target, output_path=args.output, password=password)
            print(f"Decrypted: {target} -> {out}")


if __name__ == "__main__":
    main()
