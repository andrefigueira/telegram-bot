terraform {
  required_version = ">= 1.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

resource "digitalocean_ssh_key" "default" {
  name       = "${var.project_name}-key"
  public_key = file(var.ssh_public_key_path)
}

resource "digitalocean_droplet" "bot" {
  name     = "${var.project_name}-bot"
  image    = "ubuntu-24-04-x64"
  size     = var.droplet_size
  region   = var.region
  ssh_keys = [digitalocean_ssh_key.default.fingerprint]

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    telegram_token     = var.telegram_token
    encryption_key     = var.encryption_key
    monero_rpc_url     = var.monero_rpc_url
    admin_ids          = var.admin_ids
    environment        = var.environment
    domain             = var.domain
    docker_compose_url = "https://raw.githubusercontent.com/${var.github_repo}/main/docker-compose.prod.yml"
  })

  tags = ["telegram-bot", var.environment]
}

resource "digitalocean_firewall" "bot" {
  name        = "${var.project_name}-firewall"
  droplet_ids = [digitalocean_droplet.bot.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.ssh_allowed_ips
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8080"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "digitalocean_project" "bot" {
  name        = var.project_name
  description = "Telegram e-commerce bot infrastructure"
  purpose     = "Service or API"
  environment = var.environment == "production" ? "Production" : "Development"
  resources   = [digitalocean_droplet.bot.urn]
}
