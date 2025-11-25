output "droplet_ip" {
  description = "Public IP of the bot droplet"
  value       = digitalocean_droplet.bot.ipv4_address
}

output "droplet_id" {
  description = "Droplet ID"
  value       = digitalocean_droplet.bot.id
}

output "health_check_url" {
  description = "Health check endpoint"
  value       = "http://${digitalocean_droplet.bot.ipv4_address}:8080/health"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh root@${digitalocean_droplet.bot.ipv4_address}"
}
