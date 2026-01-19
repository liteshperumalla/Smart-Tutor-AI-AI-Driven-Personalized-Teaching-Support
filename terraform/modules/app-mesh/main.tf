# AWS App Mesh Module for Service Mesh
# Provides service discovery, traffic management, and observability

# App Mesh Service Mesh
resource "aws_appmesh_mesh" "main" {
  name = "${var.project_name}-${var.environment}-mesh"

  spec {
    egress_filter {
      type = "ALLOW_ALL"
    }

    # Enable service discovery
    service_discovery {
      ip_preference = "IPv4_ONLY"
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-app-mesh"
    }
  )
}

# Virtual Gateway for external ingress
resource "aws_appmesh_virtual_gateway" "main" {
  name      = "${var.project_name}-${var.environment}-vgw"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    listener {
      port_mapping {
        port     = 443
        protocol = "http"
      }

      # Health check
      health_check {
        healthy_threshold   = 2
        interval_millis     = 5000
        path                = "/health"
        port                = 443
        protocol            = "http"
        timeout_millis      = 2000
        unhealthy_threshold = 2
      }

      # TLS configuration
      dynamic "tls" {
        for_each = var.enable_mtls ? [1] : []

        content {
          mode = "STRICT"

          certificate {
            acm {
              certificate_arn = var.certificate_arn
            }
          }
        }
      }
    }

    # Access logging
    logging {
      access_log {
        file {
          path = "/dev/stdout"
        }
      }
    }
  }

  tags = var.common_tags
}

# Virtual Nodes for each microservice

# Auth Service Virtual Node
resource "aws_appmesh_virtual_node" "auth_service" {
  name      = "${var.project_name}-${var.environment}-auth-service-vn"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    # Backend (services this node depends on)
    backend {
      virtual_service {
        virtual_service_name = aws_appmesh_virtual_service.user_db.virtual_service_name
      }
    }

    backend {
      virtual_service {
        virtual_service_name = aws_appmesh_virtual_service.redis_cache.virtual_service_name
      }
    }

    # Listener
    listener {
      port_mapping {
        port     = 8000
        protocol = "http"
      }

      health_check {
        healthy_threshold   = 2
        interval_millis     = 5000
        path                = "/health/ready"
        port                = 8000
        protocol            = "http"
        timeout_millis      = 2000
        unhealthy_threshold = 2
      }

      # Connection pool
      connection_pool {
        http {
          max_connections      = 100
          max_pending_requests = 100
        }
      }

      # Timeout
      timeout {
        idle {
          unit  = "s"
          value = 60
        }
      }

      # Outlier detection
      outlier_detection {
        max_ejection_percent = 50
        max_server_errors    = 5

        interval {
          unit  = "s"
          value = 10
        }

        base_ejection_duration {
          unit  = "s"
          value = 30
        }
      }
    }

    # Service discovery via Cloud Map
    service_discovery {
      aws_cloud_map {
        namespace_name = var.cloud_map_namespace_name
        service_name   = "auth-service"

        attributes = {
          ECS_SERVICE_NAME = "auth-service"
        }
      }
    }

    # Logging
    logging {
      access_log {
        file {
          path = "/dev/stdout"
        }
      }
    }
  }

  tags = var.common_tags
}

# Chat Service Virtual Node
resource "aws_appmesh_virtual_node" "chat_service" {
  name      = "${var.project_name}-${var.environment}-chat-service-vn"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    backend {
      virtual_service {
        virtual_service_name = aws_appmesh_virtual_service.dynamodb.virtual_service_name
      }
    }

    backend {
      virtual_service {
        virtual_service_name = aws_appmesh_virtual_service.bedrock.virtual_service_name
      }
    }

    listener {
      port_mapping {
        port     = 8000
        protocol = "http"
      }

      health_check {
        healthy_threshold   = 2
        interval_millis     = 5000
        path                = "/health/ready"
        port                = 8000
        protocol            = "http"
        timeout_millis      = 2000
        unhealthy_threshold = 2
      }

      connection_pool {
        http {
          max_connections      = 200
          max_pending_requests = 200
        }
      }
    }

    service_discovery {
      aws_cloud_map {
        namespace_name = var.cloud_map_namespace_name
        service_name   = "chat-service"
      }
    }

    logging {
      access_log {
        file {
          path = "/dev/stdout"
        }
      }
    }
  }

  tags = var.common_tags
}

# Virtual Routers

# Auth Service Virtual Router
resource "aws_appmesh_virtual_router" "auth_service" {
  name      = "${var.project_name}-${var.environment}-auth-service-vr"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    listener {
      port_mapping {
        port     = 8000
        protocol = "http"
      }
    }
  }

  tags = var.common_tags
}

# Routes

# Auth Service Route
resource "aws_appmesh_route" "auth_service" {
  name                = "${var.project_name}-${var.environment}-auth-service-route"
  mesh_name           = aws_appmesh_mesh.main.name
  virtual_router_name = aws_appmesh_virtual_router.auth_service.name

  spec {
    http_route {
      match {
        prefix = "/"
      }

      action {
        weighted_target {
          virtual_node = aws_appmesh_virtual_node.auth_service.name
          weight       = 100
        }
      }

      # Retry policy
      retry_policy {
        max_retries = 3

        per_retry_timeout {
          unit  = "s"
          value = 5
        }

        http_retry_events = [
          "server-error",
        ]

        tcp_retry_events = [
          "connection-error",
        ]
      }

      # Timeout
      timeout {
        idle {
          unit  = "s"
          value = 60
        }

        per_request {
          unit  = "s"
          value = 15
        }
      }
    }
  }
}

# Virtual Services

# Auth Service Virtual Service
resource "aws_appmesh_virtual_service" "auth_service" {
  name      = "auth-service.${var.cloud_map_namespace_name}"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    provider {
      virtual_router {
        virtual_router_name = aws_appmesh_virtual_router.auth_service.name
      }
    }
  }

  tags = var.common_tags
}

# Database Virtual Services (for backend dependencies)

resource "aws_appmesh_virtual_service" "user_db" {
  name      = "user-db.${var.cloud_map_namespace_name}"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    provider {
      virtual_node {
        virtual_node_name = "user-db-vn"  # Would need to create this
      }
    }
  }

  tags = var.common_tags
}

resource "aws_appmesh_virtual_service" "dynamodb" {
  name      = "dynamodb.${var.cloud_map_namespace_name}"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    provider {
      virtual_node {
        virtual_node_name = "dynamodb-vn"
      }
    }
  }

  tags = var.common_tags
}

resource "aws_appmesh_virtual_service" "redis_cache" {
  name      = "redis-cache.${var.cloud_map_namespace_name}"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    provider {
      virtual_node {
        virtual_node_name = "redis-cache-vn"
      }
    }
  }

  tags = var.common_tags
}

resource "aws_appmesh_virtual_service" "bedrock" {
  name      = "bedrock.${var.cloud_map_namespace_name}"
  mesh_name = aws_appmesh_mesh.main.name

  spec {
    provider {
      virtual_node {
        virtual_node_name = "bedrock-vn"
      }
    }
  }

  tags = var.common_tags
}

# Cloud Map Namespace (for service discovery)
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = var.cloud_map_namespace_name
  description = "Service discovery namespace for ${var.project_name}"
  vpc         = var.vpc_id

  tags = var.common_tags
}

# Cloud Map Services

resource "aws_service_discovery_service" "auth_service" {
  name = "auth-service"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = var.common_tags
}

resource "aws_service_discovery_service" "chat_service" {
  name = "chat-service"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = var.common_tags
}
