# Encryption at Rest

## Overview

Sensitive data is encrypted before storage using libsodium's authenticated encryption. This protects user data even if the database file is compromised.

## Encrypted Fields

| Model | Field | Contains |
|-------|-------|----------|
| Order | delivery_address | User's delivery information |
| Order | notes | Order notes and instructions |

## Encryption Implementation

### Key Management

```python
import os
import base64

def get_encryption_key() -> bytes:
    """Load encryption key from environment."""
    key_b64 = os.environ.get("ENCRYPTION_KEY")
    if not key_b64:
        raise ValueError("ENCRYPTION_KEY not configured")

    key = base64.b64decode(key_b64)
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must be 32 bytes")

    return key
```

### Encryption Functions

```python
import base64
from nacl import secret

def encrypt(plain: str, key: str) -> str:
    """Encrypt text with base64 key."""
    box = secret.SecretBox(base64.b64decode(key))
    encrypted = box.encrypt(plain.encode())
    return base64.b64encode(encrypted).decode()

def decrypt(ciphertext: str, key: str) -> str:
    """Decrypt text with base64 key."""
    box = secret.SecretBox(base64.b64decode(key))
    decrypted = box.decrypt(base64.b64decode(ciphertext))
    return decrypted.decode()
```

Note: The key is passed as a base64-encoded string from the `ENCRYPTION_KEY` environment variable.

### Model Integration

The Order model stores encrypted addresses directly:

```python
class Order(SQLModel, table=True):
    address_encrypted: str  # Encrypted at creation time

# Encrypt before storing
from bot.models import encrypt
from bot.config import get_settings

settings = get_settings()
order = Order(
    product_id=1,
    vendor_id=1,
    quantity=2,
    payment_id="abc123",
    address_encrypted=encrypt(user_address, settings.encryption_key)
)

# Decrypt when reading
from bot.models import decrypt
plain_address = decrypt(order.address_encrypted, settings.encryption_key)
```

## Cryptographic Details

### Algorithm

**XSalsa20-Poly1305** via libsodium:
- XSalsa20: Stream cipher for confidentiality
- Poly1305: MAC for authentication
- Combined: Authenticated encryption (AEAD)

### Properties

| Property | Value |
|----------|-------|
| Key Size | 256 bits (32 bytes) |
| Nonce Size | 192 bits (24 bytes) |
| MAC Size | 128 bits (16 bytes) |
| Overhead | 40 bytes per encrypted field |

### Nonce Generation

PyNaCl automatically generates a random nonce for each encryption operation. The nonce is prepended to the ciphertext.

```
[24-byte nonce][16-byte MAC][ciphertext]
```

## Key Generation

### Secure Key Generation

```bash
# Using OpenSSL
openssl rand -base64 32

# Using Python
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Key Storage

Store the key securely:

```bash
# Environment variable (recommended)
export ENCRYPTION_KEY="base64encodedkey=="

# Docker secrets
echo "base64encodedkey==" | docker secret create encryption_key -

# .env file (development only)
ENCRYPTION_KEY=base64encodedkey==
```

## Key Rotation

### Rotation Process

```python
async def rotate_encryption_key(old_key: bytes, new_key: bytes) -> None:
    """Re-encrypt all data with a new key."""
    with Session(engine) as session:
        orders = session.exec(select(Order)).all()

        for order in orders:
            # Decrypt with old key
            if order._delivery_address:
                plaintext = decrypt_field(order._delivery_address, old_key)
                order._delivery_address = encrypt_field(plaintext, new_key)

            if order._notes:
                plaintext = decrypt_field(order._notes, old_key)
                order._notes = encrypt_field(plaintext, new_key)

        session.commit()
```

### Rotation Steps

1. Generate new encryption key
2. Stop accepting new orders
3. Run rotation script
4. Update `ENCRYPTION_KEY` in environment
5. Restart application
6. Verify decryption works
7. Securely delete old key

## Security Considerations

### Do

- Use cryptographically secure random key generation
- Store keys in environment variables or secrets manager
- Rotate keys periodically
- Log key rotation events (without logging the key)

### Don't

- Hardcode keys in source code
- Log plaintext sensitive data
- Store keys in the database
- Reuse keys across environments
