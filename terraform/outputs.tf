output "k8s_control_ip" {
  value = hcloud_server.k8s_control.ipv4_address
}

output "worker_1_ip" {
  value = hcloud_server.k8s_worker_1.ipv4_address
}

output "worker_2_ip" {
  value = hcloud_server.k8s_worker_2.ipv4_address
}

output "api_endpoint" {
  value = "https://api.${var.domain}"
}

output "app_endpoint" {
  value = "https://app.${var.domain}"
}
