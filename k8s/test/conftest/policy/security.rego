package main

# METADATA
# title: Security Policies for Kubernetes Resources
# description: Enforce security best practices for Kubernetes deployments
# custom:
#   severity: high

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# Deny containers running as root
deny[msg] {
    input.kind == "Deployment"
    not input.spec.template.spec.securityContext.runAsNonRoot
    msg := sprintf("Container must not run as root: %s", [input.metadata.name])
}

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.securityContext.runAsNonRoot
    msg := sprintf("Container %s must explicitly set runAsNonRoot: true", [container.name])
}

# Deny privilege escalation
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    container.securityContext.allowPrivilegeEscalation != false
    msg := sprintf("Container %s must disable privilege escalation", [container.name])
}

# Deny privileged containers
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("Container %s must not be privileged", [container.name])
}

# Require capabilities to be dropped
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.securityContext.capabilities.drop
    msg := sprintf("Container %s must drop capabilities", [container.name])
}

warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    capabilities := container.securityContext.capabilities.drop
    not contains(capabilities, "ALL")
    msg := sprintf("Container %s should drop ALL capabilities", [container.name])
}

# Require read-only root filesystem where possible
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.securityContext.readOnlyRootFilesystem
    msg := sprintf("Container %s should use read-only root filesystem when possible", [container.name])
}

# Deny containers without resource limits
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits
    msg := sprintf("Container %s must have resource limits", [container.name])
}

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits.cpu
    msg := sprintf("Container %s must have CPU limit", [container.name])
}

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits.memory
    msg := sprintf("Container %s must have memory limit", [container.name])
}

# Require resource requests
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.requests
    msg := sprintf("Container %s must have resource requests", [container.name])
}

# Deny latest image tag
deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    endswith(container.image, ":latest")
    msg := sprintf("Container %s must not use 'latest' tag", [container.name])
}

warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not contains(container.image, ":")
    msg := sprintf("Container %s should specify image tag explicitly", [container.name])
}

# Require liveness probe
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.livenessProbe
    msg := sprintf("Container %s should have liveness probe", [container.name])
}

# Require readiness probe
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.readinessProbe
    msg := sprintf("Container %s should have readiness probe", [container.name])
}

# Deny containers pulling images without authentication
warn[msg] {
    input.kind == "Deployment"
    not input.spec.template.spec.imagePullSecrets
    count(input.spec.template.spec.containers) > 0
    msg := "Deployment should specify imagePullSecrets for private registries"
}

# Require security context at pod level
warn[msg] {
    input.kind == "Deployment"
    not input.spec.template.spec.securityContext
    msg := sprintf("Deployment %s should define pod-level securityContext", [input.metadata.name])
}

# Require service account
warn[msg] {
    input.kind == "Deployment"
    not input.spec.template.spec.serviceAccountName
    msg := sprintf("Deployment %s should specify serviceAccountName", [input.metadata.name])
}

# Deny automountServiceAccountToken unless explicitly needed
warn[msg] {
    input.kind == "Deployment"
    input.spec.template.spec.automountServiceAccountToken == true
    msg := sprintf("Deployment %s should explicitly set automountServiceAccountToken to false unless needed", [input.metadata.name])
}

# Check for hostPath volumes
deny[msg] {
    input.kind == "Deployment"
    volume := input.spec.template.spec.volumes[_]
    volume.hostPath
    msg := sprintf("Deployment %s must not use hostPath volumes", [input.metadata.name])
}

# Check for hostNetwork
deny[msg] {
    input.kind == "Deployment"
    input.spec.template.spec.hostNetwork == true
    msg := sprintf("Deployment %s must not use host network", [input.metadata.name])
}

# Check for hostPID
deny[msg] {
    input.kind == "Deployment"
    input.spec.template.spec.hostPID == true
    msg := sprintf("Deployment %s must not use host PID namespace", [input.metadata.name])
}

# Check for hostIPC
deny[msg] {
    input.kind == "Deployment"
    input.spec.template.spec.hostIPC == true
    msg := sprintf("Deployment %s must not use host IPC namespace", [input.metadata.name])
}
