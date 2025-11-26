variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "telegram-bot"
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "lon1"
}

variable "droplet_size" {
  description = "Droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "ssh_allowed_ips" {
  description = "IPs allowed to SSH into the droplet"
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

variable "github_repo" {
  description = "GitHub repo in format owner/repo"
  type        = string
}

variable "environment" {
  description = "Environment (development or production)"
  type        = string
  default     = "production"
}

# Bot configuration
variable "telegram_token" {
  description = "Telegram bot token"
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "32-byte base64 encryption key"
  type        = string
  sensitive   = true
}

variable "monero_rpc_url" {
  description = "Monero wallet RPC URL (internal Docker network)"
  type        = string
  default     = "http://monero-wallet:18083"
}

variable "monero_wallet_password" {
  description = "Password for the Monero wallet"
  type        = string
  sensitive   = true
}

variable "monero_rpc_user" {
  description = "Monero RPC username"
  type        = string
  default     = "monero"
}

variable "monero_rpc_password" {
  description = "Monero RPC password"
  type        = string
  sensitive   = true
}

variable "admin_ids" {
  description = "Comma-separated Telegram admin IDs"
  type        = string
}

variable "super_admin_ids" {
  description = "Comma-separated Telegram super admin IDs"
  type        = string
  default     = ""
}

variable "totp_secret" {
  description = "TOTP secret for 2FA (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "domain" {
  description = "Domain name for the API (e.g., api.darkpool.shop)"
  type        = string
  default     = ""
}

variable "dockerhub_username" {
  description = "Docker Hub username"
  type        = string
  sensitive   = true
}

variable "dockerhub_token" {
  description = "Docker Hub access token"
  type        = string
  sensitive   = true
}

# MySQL Configuration
variable "mysql_root_password" {
  description = "MySQL root password"
  type        = string
  sensitive   = true
}

variable "mysql_database" {
  description = "MySQL database name"
  type        = string
  default     = "telegram_bot"
}

variable "mysql_user" {
  description = "MySQL user"
  type        = string
  default     = "bot"
}

variable "mysql_password" {
  description = "MySQL user password"
  type        = string
  sensitive   = true
}
