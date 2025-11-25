# Monero RPC Integration

## Wallet RPC Setup

### Running Monero Wallet RPC

```bash
# Start wallet RPC (mainnet)
monero-wallet-rpc \
    --wallet-file /path/to/wallet \
    --password "wallet_password" \
    --rpc-bind-port 18082 \
    --rpc-login user:password \
    --confirm-external-bind

# Stagenet (for testing)
monero-wallet-rpc \
    --stagenet \
    --wallet-file /path/to/stagenet-wallet \
    --password "wallet_password" \
    --rpc-bind-port 38082
```

### Docker Setup

```yaml
services:
  monero-wallet:
    image: monero-wallet-rpc:latest
    volumes:
      - ./wallet:/wallet
    ports:
      - "18082:18082"
    command: >
      --wallet-file /wallet/shop
      --password ${WALLET_PASSWORD}
      --rpc-bind-port 18082
      --rpc-login ${RPC_USER}:${RPC_PASSWORD}
      --disable-rpc-login
```

## RPC Methods Used

### make_integrated_address

Creates a unique payment address with embedded payment ID.

**Implementation**:
```python
from monero.wallet import Wallet

def create_address(self) -> Tuple[str, str]:
    payment_id = uuid.uuid4().hex
    wallet = Wallet(self.settings.monero_rpc_url)
    address = wallet.make_integrated_address(payment_id=payment_id)
    return str(address), payment_id
```

**Response** (from Monero RPC):
```json
{
    "integrated_address": "4JxzBD7SXvABLnYg...",
    "payment_id": "1234567890abcdef"
}
```

### incoming (check payments)

Retrieves incoming transfers filtered by payment ID.

**Implementation**:
```python
from monero.wallet import Wallet

def check_paid(self, payment_id: str, expected_amount: Decimal = None) -> bool:
    wallet = Wallet(self.settings.monero_rpc_url)
    transfers = wallet.incoming(payment_id=payment_id)

    if not transfers:
        return False

    total_received = sum(t.amount for t in transfers)

    if expected_amount and total_received < expected_amount:
        return False

    return True
```

The `monero` Python library wraps the RPC calls and returns transfer objects with amount, confirmations, etc.

### get_balance

Check wallet balance.

**Request**:
```python
async def get_balance(self) -> tuple[Decimal, Decimal]:
    response = await self._rpc_call("get_balance", {})
    return (
        Decimal(response["balance"]) / Decimal("1e12"),
        Decimal(response["unlocked_balance"]) / Decimal("1e12")
    )
```

## RPC Client Implementation

```python
import aiohttp
from decimal import Decimal

class MoneroRPCClient:
    def __init__(self, url: str, user: str | None = None, password: str | None = None):
        self.url = url
        self.auth = aiohttp.BasicAuth(user, password) if user else None

    async def _rpc_call(self, method: str, params: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": method,
            "params": params
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url,
                json=payload,
                auth=self.auth
            ) as response:
                data = await response.json()

                if "error" in data:
                    raise MoneroRPCError(data["error"]["message"])

                return data["result"]
```

## Payment Verification

### Checking for Payment

```python
async def verify_payment(
    self,
    payment_id: str,
    expected_amount: Decimal,
    min_confirmations: int = 10
) -> PaymentStatus:
    transfers = await self.get_incoming_transfers()

    for transfer in transfers:
        if transfer["payment_id"] != payment_id:
            continue

        received = Decimal(transfer["amount"]) / Decimal("1e12")
        confirmations = transfer.get("confirmations", 0)

        if received < expected_amount:
            return PaymentStatus.UNDERPAID

        if confirmations < min_confirmations:
            return PaymentStatus.CONFIRMING

        return PaymentStatus.CONFIRMED

    return PaymentStatus.NOT_FOUND
```

### Payment Monitoring Loop

```python
async def payment_monitor(self):
    """Background task to check pending payments."""
    while True:
        pending_orders = await self.get_pending_orders()

        for order in pending_orders:
            status = await self.verify_payment(
                order.payment_id,
                order.total
            )

            if status == PaymentStatus.CONFIRMED:
                await self.confirm_order(order.id)
            elif status == PaymentStatus.EXPIRED:
                await self.expire_order(order.id)

        await asyncio.sleep(60)  # Check every minute
```

## Error Handling

```python
class MoneroRPCError(Exception):
    """Base exception for RPC errors."""

class WalletNotOpenError(MoneroRPCError):
    """Wallet file not open."""

class ConnectionError(MoneroRPCError):
    """Cannot connect to RPC."""

async def safe_rpc_call(self, method: str, params: dict) -> dict | None:
    try:
        return await self._rpc_call(method, params)
    except aiohttp.ClientError as e:
        logger.error(f"RPC connection error: {e}")
        return None
    except MoneroRPCError as e:
        logger.error(f"RPC error: {e}")
        return None
```
