# ElastiCache Redis Module

This Terraform module creates a production-ready Amazon ElastiCache Redis cluster with automatic failover, encryption, and comprehensive monitoring.

## Features

- ✅ **Multi-AZ Deployment** - Automatic failover across availability zones
- ✅ **Encryption** - At rest (KMS) and in transit (TLS)
- ✅ **Auth Token** - Redis AUTH for secure connections
- ✅ **Automated Backups** - Daily snapshots with configurable retention
- ✅ **CloudWatch Monitoring** - Comprehensive metrics and alarms
- ✅ **CloudWatch Logs** - Slow queries and engine logs
- ✅ **Performance Optimized** - Tuned parameter group
- ✅ **Auto Minor Upgrades** - Automatic security patches

## Usage

### Production Setup

```hcl
module "redis" {
  source = "./modules/elasticache"

  project_name       = "smart-tutor"
  environment        = "prod"
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.redis_sg_id]

  # Cluster configuration
  node_type            = "cache.t4g.medium"
  num_cache_nodes      = 2
  multi_az_enabled     = true
  automatic_failover_enabled = true

  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  auth_token                 = var.redis_auth_token

  # Backups
  enable_snapshot          = true
  snapshot_retention_limit = 7

  # Alarms
  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = {
    Terraform = "true"
    Project   = "smart-tutor"
  }
}
```

### Development Setup

```hcl
module "redis_dev" {
  source = "./modules/elasticache"

  project_name       = "smart-tutor"
  environment        = "dev"
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.redis_sg_id]

  # Smaller instance for dev
  node_type       = "cache.t4g.micro"
  num_cache_nodes = 1

  # Disable high availability for cost savings
  multi_az_enabled           = false
  automatic_failover_enabled = false

  # Disable encryption for easier debugging
  at_rest_encryption_enabled = false
  transit_encryption_enabled = false
  auth_token_enabled         = false

  # Shorter backup retention
  enable_snapshot          = true
  snapshot_retention_limit = 3
  skip_final_snapshot      = true
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
| subnet_ids | List of subnet IDs | `list(string)` | n/a | yes |
| security_group_ids | List of security group IDs | `list(string)` | n/a | yes |
| engine_version | Redis engine version | `string` | `"7.1"` | no |
| node_type | Instance class | `string` | `"cache.t4g.medium"` | no |
| num_cache_nodes | Number of cache nodes | `number` | `2` | no |
| automatic_failover_enabled | Enable automatic failover | `bool` | `true` | no |
| multi_az_enabled | Enable Multi-AZ | `bool` | `true` | no |
| at_rest_encryption_enabled | Enable encryption at rest | `bool` | `true` | no |
| transit_encryption_enabled | Enable TLS encryption | `bool` | `true` | no |
| auth_token_enabled | Enable Redis AUTH | `bool` | `true` | no |
| auth_token | Redis AUTH token | `string` | `null` | no |
| enable_snapshot | Enable automated snapshots | `bool` | `true` | no |
| snapshot_retention_limit | Snapshot retention days | `number` | `7` | no |

See [variables.tf](./variables.tf) for complete list of inputs.

## Outputs

| Name | Description |
|------|-------------|
| primary_endpoint_address | Primary endpoint address |
| reader_endpoint_address | Reader endpoint address |
| port | Redis port number |
| connection_string | Redis connection string |
| connection_params | Connection parameters object |

See [outputs.tf](./outputs.tf) for complete list of outputs.

## CloudWatch Alarms

The module creates the following CloudWatch alarms:

| Alarm | Metric | Threshold | Description |
|-------|--------|-----------|-------------|
| CPU Utilization | CPUUtilization | 75% | Triggers when CPU > 75% |
| Memory | DatabaseMemoryUsagePercentage | 90% | Triggers when memory usage > 90% |
| Evictions | Evictions | 1000 | Triggers when > 1000 evictions in 5 min |
| Replication Lag | ReplicationLag | 30s | Triggers when lag > 30 seconds |
| Connections | CurrConnections | 65000 | Triggers when connections > 65K |
| Cache Hit Rate | CacheHits/Total | < 80% | Triggers when hit rate < 80% |

## Parameter Group

The module includes optimized Redis parameters:

- **Memory Management**:
  - `maxmemory-policy`: allkeys-lru (evict oldest keys)
  - Configurable based on workload

- **Persistence**:
  - `appendonly`: yes (when snapshots enabled)
  - Ensures data durability

- **Performance**:
  - `timeout`: 300s (connection timeout)
  - `tcp-keepalive`: 300s (keepalive interval)

- **Monitoring**:
  - `slowlog-log-slower-than`: 10ms
  - `slowlog-max-len`: 128 entries
  - `notify-keyspace-events`: Ex (expired events)

## Connection Examples

### Python (redis-py)

```python
import redis
from ssl import CERT_REQUIRED

# With encryption and auth
r = redis.Redis(
    host='<primary_endpoint_address>',
    port=6379,
    password='<auth_token>',
    ssl=True,
    ssl_cert_reqs=CERT_REQUIRED,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30,
)

# Test connection
r.ping()
```

### Node.js (ioredis)

```javascript
const Redis = require('ioredis');

const redis = new Redis({
  host: '<primary_endpoint_address>',
  port: 6379,
  password: '<auth_token>',
  tls: {
    checkServerIdentity: () => undefined,
  },
  retryStrategy: (times) => {
    return Math.min(times * 50, 2000);
  },
  maxRetriesPerRequest: 3,
});

redis.on('connect', () => console.log('Connected to Redis'));
redis.on('error', (err) => console.error('Redis error:', err));
```

### Environment Variables

```bash
export REDIS_HOST="<primary_endpoint_address>"
export REDIS_PORT="6379"
export REDIS_PASSWORD="<auth_token>"
export REDIS_SSL="true"
```

## Cost Estimation

### Production Setup (cache.t4g.medium, 2 nodes)

```
Instance costs (2 nodes):           ~$95/month
Data transfer:                      ~$10/month
Snapshots (100GB):                  ~$5/month
-----------------------------------------------------
Total:                              ~$110/month
```

### Development Setup (cache.t4g.micro, 1 node)

```
Instance costs (1 node):            ~$12/month
Data transfer:                      ~$2/month
Snapshots (10GB):                   ~$1/month
-----------------------------------------------------
Total:                              ~$15/month
```

## Best Practices

### Production

1. **Always use Multi-AZ** for automatic failover
2. **Enable encryption** at rest and in transit
3. **Use AUTH tokens** for secure authentication
4. **Enable automated snapshots** with 7+ days retention
5. **Set up CloudWatch alarms** with SNS notifications
6. **Monitor cache hit rate** (target > 80%)
7. **Use reader endpoint** for read-heavy workloads
8. **Regular backup testing** - verify restore procedures

### Development

1. **Single node** is acceptable for dev/test
2. **Disable encryption** for easier debugging (if needed)
3. **Shorter retention** periods (3-5 days) to save costs
4. **Smaller instance types** (cache.t4g.micro/small)
5. **Skip final snapshots** for temporary environments

### Performance Tuning

1. **Choose appropriate maxmemory-policy**:
   - `allkeys-lru`: Good for caching (evict least recently used)
   - `volatile-ttl`: Evict keys with TTL first
   - `noeviction`: Return errors when memory full

2. **Monitor evictions**: High evictions indicate insufficient memory
3. **Track cache hit rate**: Low hit rate suggests cache warming issues
4. **Use pipelining**: Batch commands for better throughput
5. **Connection pooling**: Reuse connections to reduce overhead

## Monitoring

### Key Metrics to Watch

1. **CPUUtilization**: Should stay < 75% for headroom
2. **DatabaseMemoryUsagePercentage**: Monitor evictions if > 90%
3. **CacheHitRate**: Target > 80% for efficient caching
4. **ReplicationLag**: Should be < 1 second normally
5. **CurrConnections**: Monitor for connection leaks
6. **NetworkBytesIn/Out**: Track data transfer costs

### CloudWatch Logs

- **Slow Log**: Queries taking > 10ms
- **Engine Log**: Redis engine events and errors

Access logs:
```bash
aws logs tail /aws/elasticache/smart-tutor-prod/redis/slow-log --follow
aws logs tail /aws/elasticache/smart-tutor-prod/redis/engine-log --follow
```

## High Availability

### Automatic Failover

With Multi-AZ enabled:
- **RTO**: ~1-2 minutes
- **RPO**: ~0 seconds (synchronous replication)
- **No data loss**: Automatic promotion of replica

### Manual Failover (for testing)

```bash
aws elasticache test-failover \
  --replication-group-id smart-tutor-prod-redis \
  --node-group-id 0001
```

## Backup and Recovery

### Automated Snapshots

- Daily snapshots during snapshot window
- Retention configurable (default 7 days)
- Stored in S3 (encrypted)

### Manual Snapshot

```bash
aws elasticache create-snapshot \
  --replication-group-id smart-tutor-prod-redis \
  --snapshot-name smart-tutor-manual-snapshot-$(date +%Y%m%d)
```

### Restore from Snapshot

```bash
aws elasticache create-replication-group \
  --replication-group-id smart-tutor-restored \
  --snapshot-name smart-tutor-manual-snapshot-20240115
```

## Security

### Network Security

- Deployed in **private subnets** only
- **Security groups** restrict access to application tier
- **No public accessibility**

### Encryption

- **At Rest**: KMS encryption for snapshots and data
- **In Transit**: TLS 1.2+ for all connections
- **AUTH Token**: Redis password authentication

### Access Control

- **VPC isolation** - No internet access
- **Least privilege** security groups
- **Auth token rotation** via Secrets Manager

## Troubleshooting

### High Memory Usage

1. Check evictions metric in CloudWatch
2. Review data size: `INFO memory` command
3. Analyze key distribution: `MEMORY STATS`
4. Consider scaling up node type
5. Review maxmemory-policy setting

### High CPU Usage

1. Check for expensive commands in slow log
2. Review connection count
3. Use `SLOWLOG GET` to analyze queries
4. Consider read replicas for read-heavy workloads
5. Enable clustering for horizontal scaling

### Connection Issues

1. Verify security group allows traffic from application
2. Check auth token is correct
3. Verify TLS configuration matches settings
4. Check connection limits (default 65,000)
5. Review engine logs for errors

### Replication Lag

1. Check network latency between AZs
2. Review write throughput
3. Check for expensive operations on replica
4. Consider scaling up node type
5. Review replication backlog size

## Maintenance

### Upgrade Procedure

1. Test upgrade in dev/staging first
2. Take manual snapshot before upgrade
3. Schedule during low-traffic window
4. Enable automatic minor version upgrades
5. Monitor for issues after upgrade

### Parameter Changes

1. Changes require reboot for some parameters
2. Use `apply_immediately = false` in production
3. Schedule changes during maintenance window
4. Test in non-production first

## Redis CLI Access

### Connect to Redis

```bash
# With encryption and auth
redis-cli -h <primary_endpoint_address> \
  -p 6379 \
  --tls \
  --cacert /path/to/aws-cert.pem \
  -a <auth_token>

# Basic commands
> PING
PONG
> INFO
> CONFIG GET maxmemory-policy
> SLOWLOG GET 10
```

## License

This module is part of the Smart AI Tutor project.
