package compliance.soc2

# SOC 2 Type II Compliance Policies
# Trust Services Criteria: Security, Availability, Processing Integrity,
# Confidentiality, and Privacy

import future.keywords.contains
import future.keywords.if
import future.keywords.in

## Security Criteria

# CC6.1 - Logical and Physical Access Controls
deny[msg] {
    input.kind == "Deployment"
    not input.spec.template.spec.securityContext.runAsNonRoot
    msg := sprintf("SOC2-CC6.1: Deployment %s must run as non-root user", [input.metadata.name])
}

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("SOC2-CC6.1: Container %s must not run in privileged mode", [container.name])
}

# CC6.6 - Logical and Physical Access Restrictions
deny[msg] {
    input.kind == "Service"
    input.spec.type == "LoadBalancer"
    not input.metadata.annotations["service.beta.kubernetes.io/aws-load-balancer-internal"]
    msg := sprintf("SOC2-CC6.6: Service %s must use internal load balancer unless explicitly approved", [input.metadata.name])
}

# CC6.7 - System Monitoring
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.livenessProbe
    not container.readinessProbe
    msg := sprintf("SOC2-CC6.7: Container %s should have health probes for monitoring", [container.name])
}

# CC7.2 - System Operation Monitoring
deny[msg] {
    input.kind == "Deployment"
    not input.metadata.annotations["prometheus.io/scrape"]
    msg := sprintf("SOC2-CC7.2: Deployment %s must have Prometheus monitoring enabled", [input.metadata.name])
}

## Availability Criteria

# A1.2 - Processing Integrity
deny[msg] {
    input.kind == "Deployment"
    input.metadata.namespace == "production"
    input.spec.replicas < 2
    msg := sprintf("SOC2-A1.2: Production deployment %s must have at least 2 replicas for high availability", [input.metadata.name])
}

deny[msg] {
    input.kind == "Deployment"
    input.metadata.namespace == "production"
    not input.spec.template.spec.affinity.podAntiAffinity
    input.spec.replicas > 1
    msg := sprintf("SOC2-A1.2: Production deployment %s must have pod anti-affinity for availability", [input.metadata.name])
}

# A1.3 - Environmental Protections
warn[msg] {
    input.kind == "PersistentVolumeClaim"
    not input.spec.storageClassName
    msg := sprintf("SOC2-A1.3: PVC %s should specify storageClassName for reliable storage", [input.metadata.name])
}

## Processing Integrity

# PI1.4 - Data Processing Integrity
deny[msg] {
    input.kind == "ConfigMap"
    input.metadata.namespace == "production"
    value := input.data[key]
    contains(lower(key), "password")
    msg := sprintf("SOC2-PI1.4: ConfigMap %s contains sensitive data in key '%s' - use Secret instead", [input.metadata.name, key])
}

deny[msg] {
    input.kind == "ConfigMap"
    input.metadata.namespace == "production"
    value := input.data[key]
    contains(lower(key), "secret")
    msg := sprintf("SOC2-PI1.4: ConfigMap %s contains sensitive data in key '%s' - use Secret instead", [input.metadata.name, key])
}

## Confidentiality

# C1.1 - Encryption at Rest
deny[msg] {
    input.kind == "PersistentVolumeClaim"
    input.metadata.namespace == "production"
    not input.metadata.annotations["encrypted"]
    msg := sprintf("SOC2-C1.1: PVC %s must use encrypted storage in production", [input.metadata.name])
}

# C1.2 - Encryption in Transit
deny[msg] {
    input.kind == "Ingress"
    not input.spec.tls
    msg := sprintf("SOC2-C1.2: Ingress %s must enforce TLS encryption", [input.metadata.name])
}

## Privacy

# P3.2 - Data Retention
warn[msg] {
    input.kind == "PersistentVolumeClaim"
    not input.metadata.annotations["retention-policy"]
    msg := sprintf("SOC2-P3.2: PVC %s should have data retention policy defined", [input.metadata.name])
}

# P4.1 - Data Disposal
warn[msg] {
    input.kind == "PersistentVolumeClaim"
    not input.metadata.annotations["disposal-method"]
    msg := sprintf("SOC2-P4.1: PVC %s should have data disposal method documented", [input.metadata.name])
}

## Change Management

# CC8.1 - Change Management Process
deny[msg] {
    input.kind == "Deployment"
    input.metadata.namespace == "production"
    not input.metadata.annotations["change-ticket"]
    not input.metadata.labels["managed-by"]
    msg := sprintf("SOC2-CC8.1: Production deployment %s must have change ticket or be managed by GitOps", [input.metadata.name])
}

## Audit Logging

# CC7.3 - Audit Logs
warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not contains(container.args[_], "audit-log")
    msg := sprintf("SOC2-CC7.3: Container %s should enable audit logging", [container.name])
}

## Network Security

# CC6.6 - Network Segmentation
deny[msg] {
    input.kind == "NetworkPolicy"
    input.spec.policyTypes[_] == "Ingress"
    count(input.spec.ingress) == 0
    input.spec.podSelector.matchLabels
    msg := sprintf("SOC2-CC6.6: NetworkPolicy %s denies all ingress but should have explicit rules", [input.metadata.name])
}

## Compliance Summary
compliance_score[score] {
    total_checks := count(deny)
    passed_checks := count(deny) - count([msg | deny[msg]])
    score := passed_checks / total_checks * 100
}
