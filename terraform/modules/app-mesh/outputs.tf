# App Mesh Module Outputs

output "mesh_id" {
  description = "ID of the App Mesh service mesh"
  value       = aws_appmesh_mesh.main.id
}

output "mesh_arn" {
  description = "ARN of the App Mesh service mesh"
  value       = aws_appmesh_mesh.main.arn
}

output "mesh_name" {
  description = "Name of the App Mesh service mesh"
  value       = aws_appmesh_mesh.main.name
}

output "virtual_gateway_arn" {
  description = "ARN of the virtual gateway"
  value       = aws_appmesh_virtual_gateway.main.arn
}

output "auth_service_virtual_node_arn" {
  description = "ARN of the auth service virtual node"
  value       = aws_appmesh_virtual_node.auth_service.arn
}

output "chat_service_virtual_node_arn" {
  description = "ARN of the chat service virtual node"
  value       = aws_appmesh_virtual_node.chat_service.arn
}

output "auth_service_virtual_service_name" {
  description = "Name of the auth service virtual service"
  value       = aws_appmesh_virtual_service.auth_service.name
}

output "cloud_map_namespace_id" {
  description = "ID of the Cloud Map namespace"
  value       = aws_service_discovery_private_dns_namespace.main.id
}

output "cloud_map_namespace_arn" {
  description = "ARN of the Cloud Map namespace"
  value       = aws_service_discovery_private_dns_namespace.main.arn
}

output "auth_service_discovery_arn" {
  description = "ARN of the auth service discovery service"
  value       = aws_service_discovery_service.auth_service.arn
}

output "chat_service_discovery_arn" {
  description = "ARN of the chat service discovery service"
  value       = aws_service_discovery_service.chat_service.arn
}
