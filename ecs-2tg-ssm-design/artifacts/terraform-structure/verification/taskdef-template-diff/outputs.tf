output "container_definitions_sha256" {
  value = sha256(local.container_definitions)
}

output "direct_container_definitions_sha256" {
  value = sha256(local.direct_container_definitions)
}

output "direct_equals_template_canonical" {
  value = local.direct_container_definitions == local.container_definitions
}
