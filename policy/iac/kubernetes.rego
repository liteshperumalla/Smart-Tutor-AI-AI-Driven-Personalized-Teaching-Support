package main

import future.keywords.in

target_kinds := {"Deployment"}
target_components := {"backend", "frontend"}

is_target_resource {
  target_kinds[input.kind]
  component := input.metadata.labels["app.kubernetes.io/component"]
  target_components[component]
}

pod_security_context := object.get(input.spec.template.spec, "securityContext", {})

container_security_context(container) := object.get(container, "securityContext", {})

container_capability_drops(container) := object.get(object.get(container_security_context(container), "capabilities", {}), "drop", [])

container_resources(container) := object.get(container, "resources", {})

container_requests(container) := object.get(container_resources(container), "requests", {})

container_limits(container) := object.get(container_resources(container), "limits", {})

deny[msg] {
  is_target_resource
  not input.spec.template.spec.serviceAccountName
  msg := sprintf("%s must set serviceAccountName", [input.metadata.name])
}

deny[msg] {
  is_target_resource
  object.get(pod_security_context, "runAsNonRoot", false) != true
  msg := sprintf("%s must set pod securityContext.runAsNonRoot=true", [input.metadata.name])
}

deny[msg] {
  is_target_resource
  object.get(object.get(pod_security_context, "seccompProfile", {}), "type", "") != "RuntimeDefault"
  msg := sprintf("%s must set pod seccompProfile.type=RuntimeDefault", [input.metadata.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_security_context(container), "runAsNonRoot", false) != true
  msg := sprintf("%s container %s must set runAsNonRoot=true", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_security_context(container), "allowPrivilegeEscalation", true) != false
  msg := sprintf("%s container %s must disable privilege escalation", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  count(container_capability_drops(container)) == 0
  msg := sprintf("%s container %s must drop Linux capabilities", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  capabilities := container_capability_drops(container)
  not "ALL" in capabilities
  msg := sprintf("%s container %s must drop ALL capabilities", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_requests(container), "cpu", "") == ""
  msg := sprintf("%s container %s must declare CPU requests", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_requests(container), "memory", "") == ""
  msg := sprintf("%s container %s must declare memory requests", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_limits(container), "cpu", "") == ""
  msg := sprintf("%s container %s must declare CPU limits", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  object.get(container_limits(container), "memory", "") == ""
  msg := sprintf("%s container %s must declare memory limits", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  not container.livenessProbe
  msg := sprintf("%s container %s must define a livenessProbe", [input.metadata.name, container.name])
}

deny[msg] {
  is_target_resource
  container := input.spec.template.spec.containers[_]
  not container.readinessProbe
  msg := sprintf("%s container %s must define a readinessProbe", [input.metadata.name, container.name])
}
