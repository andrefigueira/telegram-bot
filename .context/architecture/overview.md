# Architecture Overview

## System Design

The bot follows a modular, service-oriented architecture with clear separation between Telegram handlers and business logic.

```mermaid
graph TB
    subgraph Telegram
        TG[Telegram API]
    end

    subgraph Bot Layer
        H[Handlers]
        H --> UH[User Handlers]
        H --> AH[Admin Handlers]
    end

    subgraph Service Layer
        S[Services]
        S --> CAT[Catalog Service]
        S --> ORD[Orders Service]
        S --> PAY[Payments Service]
        S --> VEN[Vendors Service]
    end

    subgraph Data Layer
        DB[(SQLite)]
        ENC[Encryption Layer]
    end

    subgraph External
        XMR[Monero RPC]
    end

    TG <--> H
    UH --> S
    AH --> S
    S --> ENC
    ENC --> DB
    PAY --> XMR
```

## Component Responsibilities

### Handlers (`bot/handlers/`)

Thin layer responsible for:
- Parsing Telegram messages and commands
- Input validation
- Calling appropriate services
- Formatting responses for Telegram

Handlers should not contain business logic.

### Services (`bot/services/`)

Business logic layer handling:
- **catalog.py**: Product CRUD operations
- **orders.py**: Order creation and management
- **payments.py**: Monero wallet integration
- **vendors.py**: Multi-vendor management

### Models (`bot/models.py`)

SQLModel definitions with:
- Field validation
- Encryption decorators for sensitive data
- Relationship definitions

## Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant T as Telegram
    participant H as Handler
    participant S as Service
    participant D as Database
    participant M as Monero RPC

    U->>T: /order product_id qty
    T->>H: Update object
    H->>H: Validate input
    H->>S: create_order()
    S->>D: Check inventory
    S->>M: Generate payment address
    M-->>S: Payment details
    S->>D: Store encrypted order
    D-->>S: Order ID
    S-->>H: Order response
    H-->>T: Format message
    T-->>U: Payment instructions
```

## Design Principles

1. **Single Responsibility**: Each module handles one concern
2. **Dependency Injection**: Services receive dependencies via constructors
3. **Fail-Safe Defaults**: Mock mode when external services unavailable
4. **Encryption by Default**: Sensitive data never stored in plaintext
