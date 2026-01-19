package main

# METADATA
# title: Resource Management Policies
# description: Enforce resource management best practices
# custom:
#   severity: medium

import future.keywords.if

# Check CPU limits are reasonable
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    cpu_limit := to_number(trim_suffix(container.resources.limits.cpu, "m"))
    cpu_limit > 4000
    msg := sprintf("Container %s CPU limit (%s) is very high, consider optimization", [container.name, container.resources.limits.cpu])
}

# Check memory limits are reasonable
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    mem_limit_str := container.resources.limits.memory
    contains(mem_limit_str, "Gi")
    mem_limit := to_number(trim_suffix(mem_limit_str, "Gi"))
    mem_limit > 8
    msg := sprintf("Container %s memory limit (%s) is very high, consider optimization", [container.name, mem_limit_str])
}

# Check requests vs limits ratio
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    cpu_request := to_number(trim_suffix(container.resources.requests.cpu, "m"))
    cpu_limit := to_number(trim_suffix(container.resources.limits.cpu, "m"))
    cpu_limit / cpu_request > 4
    msg := sprintf("Container %s has CPU limit/request ratio > 4x, may cause throttling", [container.name])
}

# Verify HPA exists for production deployments
warn[msg] {
    input.kind == "Deployment"
    input.metadata.namespace == "production"
    input.spec.replicas > 3
    msg := sprintf("Production deployment %s with >3 replicas should have HPA", [input.metadata.name])
}

# Check PDB exists for critical services
warn[msg] {
    input.kind == "Deployment"
    input.metadata.labels.tier == "critical"
    msg := sprintf("Critical deployment %s should have PodDisruptionBudget", [input.metadata.name])
}

# Verify anti-affinity for HA
warn[msg] {
    input.kind == "Deployment"
    input.metadata.namespace == "production"
    input.spec.replicas > 1
    not input.spec.template.spec.affinity.podAntiAffinity
    msg := sprintf("Production deployment %s with multiple replicas should have pod anti-affinity", [input.metadata.name])
}
