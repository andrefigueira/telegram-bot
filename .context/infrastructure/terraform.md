# Terraform Configuration

## Directory Structure

```
terraform/
  main.tf                 # Provider, resources, firewall
  variables.tf            # Input variable definitions
  outputs.tf              # Output values
  cloud-init.yaml         # Server bootstrap script
  terraform.tfvars.example # Example configuration
  .gitignore              # Ignore state and secrets
```

## Resources Created

### digitalocean_droplet.bot

The main compute instance running the bot.

- **Image**: Ubuntu 24.04 LTS
- **User Data**: cloud-init script for automated setup
- **Tags**: `telegram-bot`, environment name

### digitalocean_firewall.bot

Network security rules:

```hcl
# SSH access (configurable source IPs)
inbound_rule {
  protocol         = "tcp"
  port_range       = "22"
  source_addresses = var.ssh_allowed_ips
}

# Health check endpoint (public)
inbound_rule {
  protocol         = "tcp"
  port_range       = "8080"
  source_addresses = ["0.0.0.0/0"]
}

# All outbound traffic allowed
outbound_rule {
  protocol              = "tcp"
  port_range            = "1-65535"
  destination_addresses = ["0.0.0.0/0"]
}
```

### digitalocean_ssh_key.default

SSH key for admin access, imported from local file.

### digitalocean_project.bot

Groups all resources in DO dashboard.

## Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| do_token | Yes | - | DigitalOcean API token |
| telegram_token | Yes | - | Telegram bot token |
| encryption_key | Yes | - | 32-byte base64 key |
| admin_ids | Yes | - | Telegram admin IDs |
| github_repo | Yes | - | Repo for docker-compose.yml |
| project_name | No | telegram-bot | Resource name prefix |
| region | No | lon1 | DO datacenter |
| droplet_size | No | s-1vcpu-1gb | VM size |
| environment | No | production | Environment name |
| monero_rpc_url | No | "" | Monero wallet RPC URL |
| ssh_public_key_path | No | ~/.ssh/id_rsa.pub | SSH key path |
| ssh_allowed_ips | No | ["0.0.0.0/0"] | IPs allowed to SSH |

## Outputs

| Output | Description |
|--------|-------------|
| droplet_ip | Public IPv4 address |
| droplet_id | DO droplet ID |
| health_check_url | Full health check URL |
| ssh_command | Ready-to-use SSH command |

## State Management

Terraform state is stored locally by default. For team usage, configure remote state:

```hcl
terraform {
  backend "s3" {
    endpoint                    = "nyc3.digitaloceanspaces.com"
    bucket                      = "your-terraform-state"
    key                         = "telegram-bot/terraform.tfstate"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
  }
}
```

## Common Operations

```bash
# Initialize (first time)
terraform init

# Preview changes
terraform plan

# Apply changes
terraform apply

# Show current state
terraform show

# Destroy all resources
terraform destroy

# Update single resource
terraform apply -target=digitalocean_droplet.bot

# Import existing resource
terraform import digitalocean_droplet.bot <droplet_id>
```
