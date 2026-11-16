variable "hcloud_token" {
  description = "Hetzner Cloud API Token"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API Token with Zone:Edit"
  type        = string
  sensitive   = true
}

variable "domain" {
  description = "Root domain for NEXORUM"
  type        = string
  default     = "nexorum.ai"
}
