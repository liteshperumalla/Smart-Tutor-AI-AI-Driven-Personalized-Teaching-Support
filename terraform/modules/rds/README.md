# RDS PostgreSQL Module

This Terraform module creates a production-ready Amazon RDS PostgreSQL instance with Multi-AZ deployment, automated backups, encryption, and comprehensive monitoring.

## Features

- ✅ **Multi-AZ Deployment** - Automatic failover for high availability
- ✅ **Automated Backups** - Point-in-time recovery with configurable retention
- ✅ **Encryption** - At rest and in transit using KMS
- ✅ **Performance Insights** - Advanced database performance monitoring
- ✅ **Enhanced Monitoring** - 60-second granularity metrics
- ✅ **CloudWatch Alarms** - Proactive monitoring and alerting
- ✅ **Read Replica Support** - Optional read replicas for scaling reads
- ✅ **Auto-Scaling Storage** - Automatic storage expansion up to limit
- ✅ **SSL/TLS Enforced** - All connections require encryption
- ✅ **Optimized Parameters** - Performance-tuned parameter group

## Usage

### Basic Usage

```hcl
module "rds" {
  source = "./modules/rds"

  project_name         = "smart-tutor"
  environment          = "prod"
  database_subnet_ids  = module.vpc.database_subnet_ids
  security_group_ids   = [module.security_groups.rds_sg_id]

  # Database Configuration
  database_name    = "smarttutor"
  master_username  = "postgres"
  master_password  = var.db_password # Store in Secrets Manager

  # Instance Configuration
  instance_class         = "db.t4g.medium"
  allocated_storage      = 100
  max_allocated_storage  = 500

  # High Availability
  multi_az = true

  # Backups
  backup_retention_period = 7
  skip_final_snapshot     = false
  deletion_protection     = true

  # Monitoring
  enhanced_monitoring_interval = 60
  performance_insights_enabled = true

  tags = {
    Terraform   = "true"
    Project     = "smart-tutor"
  }
}
```

### With Read Replica

```hcl
module "rds" {
  source = "./modules/rds"

  # ... other configuration ...

  # Read Replica
  create_read_replica     = true
  replica_instance_class  = "db.t4g.medium"
}
```

### Development Environment

```hcl
module "rds_dev" {
  source = "./modules/rds"

  project_name         = "smart-tutor"
  environment          = "dev"
  database_subnet_ids  = module.vpc.database_subnet_ids
  security_group_ids   = [module.security_groups.rds_sg_id]

  # Smaller instance for dev
  instance_class        = "db.t4g.micro"
  allocated_storage     = 20
  max_allocated_storage = 50

  # Single-AZ for cost savings
  multi_az = false

  # Shorter backup retention
  backup_retention_period = 3

  # Disable deletion protection for dev
  deletion_protection = false
  skip_final_snapshot = true

  # Disable performance insights to save cost
  performance_insights_enabled = false
  enhanced_monitoring_interval = 0
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | >= 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | >= 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment (dev, staging, prod) | `string` | n/a | yes |
| database_subnet_ids | List of subnet IDs for DB subnet group | `list(string)` | n/a | yes |
| security_group_ids | List of security group IDs | `list(string)` | n/a | yes |
| database_name | Name of the default database | `string` | `"smarttutor"` | no |
| master_username | Master username | `string` | `"postgres"` | no |
| master_password | Master password | `string` | n/a | yes |
| postgres_version | PostgreSQL version | `string` | `"15.4"` | no |
| instance_class | RDS instance class | `string` | `"db.t4g.medium"` | no |
| allocated_storage | Allocated storage in GB | `number` | `100` | no |
| max_allocated_storage | Max storage for autoscaling | `number` | `500` | no |
| multi_az | Enable Multi-AZ | `bool` | `true` | no |
| backup_retention_period | Backup retention in days | `number` | `7` | no |
| deletion_protection | Enable deletion protection | `bool` | `true` | no |
| performance_insights_enabled | Enable Performance Insights | `bool` | `true` | no |
| create_read_replica | Create read replica | `bool` | `false` | no |

See [variables.tf](./variables.tf) for complete list of inputs.

## Outputs

| Name | Description |
|------|-------------|
| db_instance_endpoint | Connection endpoint |
| db_instance_address | Hostname |
| db_instance_port | Port number |
| connection_string | PostgreSQL connection string |
| connection_params | Connection parameters object |
| db_replica_endpoint | Read replica endpoint (if enabled) |

See [outputs.tf](./outputs.tf) for complete list of outputs.

## CloudWatch Alarms

The module creates the following CloudWatch alarms:

| Alarm | Metric | Threshold | Description |
|-------|--------|-----------|-------------|
| CPU Utilization | CPUUtilization | 80% | Triggers when CPU > 80% |
| Memory | FreeableMemory | 1 GB | Triggers when free memory < 1GB |
| Storage | FreeStorageSpace | 10 GB | Triggers when free storage < 10GB |
| Connections | DatabaseConnections | 80% of max | Triggers when connections > 80% |
| Read Latency | ReadLatency | 100ms | Triggers when read latency > 100ms |
| Write Latency | WriteLatency | 100ms | Triggers when write latency > 100ms |

## Parameter Group Optimizations

The module includes a PostgreSQL parameter group with the following optimizations:

- **Memory Settings**:
  - `shared_buffers`: 25% of instance memory
  - `effective_cache_size`: 50% of instance memory
  - `work_mem`: 10MB per operation

- **Checkpoint Settings**:
  - `checkpoint_completion_target`: 0.9
  - `wal_buffers`: 16MB
  - `min_wal_size`: 2GB
  - `max_wal_size`: 8GB

- **SSD Optimizations**:
  - `random_page_cost`: 1.1
  - `effective_io_concurrency`: 200

- **Logging**:
  - Logs queries slower than 1 second
  - Logs connections and disconnections
  - Logs lock waits

- **Security**:
  - SSL/TLS enforced for all connections

## Best Practices

### Production

1. **Always use Multi-AZ** for high availability
2. **Enable deletion protection** to prevent accidental deletion
3. **Use strong passwords** and store in AWS Secrets Manager
4. **Enable Performance Insights** for troubleshooting
5. **Set up CloudWatch alarms** with SNS notifications
6. **Enable automated backups** with at least 7 days retention
7. **Use encryption** for data at rest and in transit
8. **Regular testing** of backup restoration

### Development

1. Use **smaller instance classes** to save costs
2. **Single-AZ deployment** is acceptable for dev/test
3. **Shorter backup retention** (3-5 days) to save storage
4. **Disable Performance Insights** if not needed
5. Can **skip final snapshot** for temporary environments

### Monitoring

1. Set up **SNS topics** for alarm notifications
2. Monitor **slow query logs** regularly
3. Review **Performance Insights** for optimization opportunities
4. Set **appropriate alarm thresholds** for your workload
5. Use **Enhanced Monitoring** for detailed metrics

## Connection Example

### Python (SQLAlchemy)

```python
from sqlalchemy import create_engine

# Using module outputs
connection_string = f"postgresql://{username}:{password}@{db_endpoint}/{database}"
engine = create_engine(
    connection_string,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    connect_args={
        'sslmode': 'require',  # Enforce SSL
        'connect_timeout': 10,
    }
)
```

### Environment Variables

```bash
# Export from Terraform outputs
export DB_HOST="<db_instance_address>"
export DB_PORT="<db_instance_port>"
export DB_NAME="<db_instance_name>"
export DB_USER="<db_instance_username>"
export DB_PASSWORD="<from_secrets_manager>"
```

## Cost Estimation

### Production Setup

```
Instance (db.t4g.medium, Multi-AZ):    ~$145/month
Storage (100GB gp3, Multi-AZ):          ~$46/month
Backup storage (100GB):                 ~$10/month
Performance Insights (7 days):          ~$7/month
Enhanced Monitoring:                    Free tier
-----------------------------------------------------
Total:                                  ~$208/month
```

### Development Setup

```
Instance (db.t4g.micro, Single-AZ):     ~$15/month
Storage (20GB gp3):                     ~$5/month
Backup storage (20GB):                  ~$2/month
-----------------------------------------------------
Total:                                  ~$22/month
```

## Disaster Recovery

### Backup Strategy

- **Automated Backups**: Daily backups with 7-day retention
- **Manual Snapshots**: Take before major changes
- **Point-in-Time Recovery**: Restore to any point within backup window
- **Cross-Region Copies**: For DR in separate region (optional)

### Recovery Procedures

1. **Restore from Snapshot**:
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier smart-tutor-restored \
     --db-snapshot-identifier <snapshot-id>
   ```

2. **Point-in-Time Restore**:
   ```bash
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier smart-tutor-prod \
     --target-db-instance-identifier smart-tutor-restored \
     --restore-time 2024-01-15T12:00:00Z
   ```

## Multi-AZ Failover

### Automatic Failover

The Multi-AZ deployment provides automatic failover with:
- **RTO**: ~1-2 minutes
- **RPO**: ~0 seconds (synchronous replication)
- **No data loss**: Synchronous replication to standby

### Manual Failover (for testing)

```bash
aws rds reboot-db-instance \
  --db-instance-identifier smart-tutor-prod \
  --force-failover
```

## Maintenance

### Recommended Schedule

- **Backup Window**: 3:00-4:00 AM UTC (low traffic)
- **Maintenance Window**: Sunday 4:00-5:00 AM UTC
- **Auto Minor Version Upgrades**: Enabled
- **Major Version Upgrades**: Manual only

### Upgrade Procedure

1. Test upgrade in dev/staging environment
2. Take manual snapshot before upgrade
3. Schedule maintenance window during low traffic
4. Monitor Performance Insights during and after
5. Have rollback plan ready

## Security

### Network Security

- Deployed in **private subnets** only
- **Security groups** restrict access to application tier
- **No public accessibility**

### Encryption

- **At Rest**: KMS encryption for storage and backups
- **In Transit**: SSL/TLS required for all connections
- **Secrets**: Password stored in AWS Secrets Manager

### Access Control

- **IAM authentication** (optional)
- **Least privilege** security group rules
- **VPC isolation** from internet

## Troubleshooting

### High CPU Usage

1. Check Performance Insights for expensive queries
2. Review slow query logs
3. Add indexes for frequently queried columns
4. Consider read replicas for read-heavy workloads
5. Scale up instance class if needed

### Storage Full

1. Module includes auto-scaling up to `max_allocated_storage`
2. Review largest tables: `SELECT * FROM pg_stat_user_tables ORDER BY n_live_tup DESC;`
3. Clean up old data or archive to S3
4. Increase `max_allocated_storage` if needed

### Connection Issues

1. Verify security group allows traffic from application
2. Check connection string and credentials
3. Verify RDS is in correct subnet group
4. Check CloudWatch Logs for connection errors

## License

This module is part of the Smart AI Tutor project.
