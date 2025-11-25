output "droplet_ip" {
  description = "Reserved IP (stable) for the bot"
  value       = digitalocean_reserved_ip.bot.ip_address
}

output "droplet_id" {
  description = "Droplet ID"
  value       = digitalocean_droplet.bot.id
}

output "health_check_url" {
  description = "Health check endpoint"
  value       = "https://${var.domain}/health"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh root@${digitalocean_reserved_ip.bot.ip_address}"
}

output "api_url" {
  description = "API URL"
  value       = "https://${var.domain}"
}
