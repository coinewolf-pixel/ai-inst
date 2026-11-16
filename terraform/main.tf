terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

# Hetzner Cloud — Kubernetes nodes (cheapest reliable EU cloud)
provider "hcloud" {
  token = var.hcloud_token
}

# Cloudflare — DNS + CDN + Pages
provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ═══════════════════════════════════════════════════════════
# HETZNER: Kubernetes Cluster
# ═══════════════════════════════════════════════════════════
resource "hcloud_network" "nexorum" {
  name     = "nexorum-network"
  ip_range = "10.0.0.0/16"
}

resource "hcloud_network_subnet" "nexorum_subnet" {
  network_id   = hcloud_network.nexorum.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.0.1.0/24"
}

# Control plane + worker nodes (CX41 = 4 vCPU, 16GB RAM, ~€15/mo)
resource "hcloud_server" "k8s_control" {
  name        = "nexorum-k8s-control"
  server_type = "cx41"
  image       = "ubuntu-22.04"
  location    = "nbg1"
  ssh_keys    = [hcloud_ssh_key.nexorum.id]
  labels = {
    role = "control-plane"
  }
}

resource "hcloud_server" "k8s_worker_1" {
  name        = "nexorum-k8s-worker-1"
  server_type = "cpx41"  # 8 vCPU, 32GB RAM
  image       = "ubuntu-22.04"
  location    = "nbg1"
  ssh_keys    = [hcloud_ssh_key.nexorum.id]
  labels = {
    role = "worker"
  }
}

resource "hcloud_server" "k8s_worker_2" {
  name        = "nexorum-k8s-worker-2"
  server_type = "cpx41"
  image       = "ubuntu-22.04"
  location    = "fsn1"
  ssh_keys    = [hcloud_ssh_key.nexorum.id]
  labels = {
    role = "worker"
  }
}

resource "hcloud_ssh_key" "nexorum" {
  name       = "nexorum-deploy-key"
  public_key = file("~/.ssh/nexorum_deploy.pub")
}

# Volumes for persistent data
resource "hcloud_volume" "postgres" {
  name      = "nexorum-postgres"
  size      = 50
  server_id = hcloud_server.k8s_worker_1.id
  format    = "ext4"
}

resource "hcloud_volume" "clickhouse" {
  name      = "nexorum-clickhouse"
  size      = 100
  server_id = hcloud_server.k8s_worker_2.id
  format    = "ext4"
}

# ═══════════════════════════════════════════════════════════
# CLOUDFLARE: DNS Records
# ═══════════════════════════════════════════════════════════
data "cloudflare_zone" "nexorum" {
  name = var.domain
}

resource "cloudflare_record" "api" {
  zone_id = data.cloudflare_zone.nexorum.id
  name    = "api"
  type    = "A"
  value   = hcloud_server.k8s_control.ipv4_address
  ttl     = 300
  proxied = true
}

resource "cloudflare_record" "app" {
  zone_id = data.cloudflare_zone.nexorum.id
  name    = "app"
  type    = "A"
  value   = hcloud_server.k8s_control.ipv4_address
  ttl     = 300
  proxied = true
}

resource "cloudflare_record" "ws" {
  zone_id = data.cloudflare_zone.nexorum.id
  name    = "ws"
  type    = "A"
  value   = hcloud_server.k8s_control.ipv4_address
  ttl     = 300
  proxied = true
}

# Cloudflare Page Rule — API caching
resource "cloudflare_page_rule" "api_cache" {
  zone_id = data.cloudflare_zone.nexorum.id
  target  = "api.${var.domain}/api/v1/market/*"
  actions {
    cache_level = "cache_everything"
    edge_cache_ttl = 60
  }
  priority = 1
}
