#!/usr/bin/env python3
"""
AWS Cost Optimization Script
Analyzes AWS resources and provides cost-saving recommendations

Features:
- EC2 instance utilization analysis
- RDS instance optimization
- Unattached EBS volumes
- Unused Elastic IPs
- Old snapshots cleanup
- Right-sizing recommendations
"""

import boto3
import json
from datetime import datetime, timedelta
from typing import List, Dict
import os

# AWS clients
cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.client('ec2')
rds = boto3.client('rds')
elbv2 = boto3.client('elbv2')
s3 = boto3.client('s3')

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')


class CostRecommendation:
    def __init__(self, resource_id: str, resource_type: str, issue: str,
                 recommendation: str, potential_savings: float):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.issue = issue
        self.recommendation = recommendation
        self.potential_savings = potential_savings

    def to_dict(self):
        return {
            'resource': self.resource_id,
            'type': self.resource_type,
            'issue': self.issue,
            'recommendation': self.recommendation,
            'potential_savings_monthly': f"${self.potential_savings:.2f}"
        }


def analyze_ec2_utilization() -> List[CostRecommendation]:
    """Find underutilized EC2 instances"""
    recommendations = []

    try:
        # Get all running instances
        instances = ec2.describe_instances(
            Filters=[
                {'Name': 'instance-state-name', 'Values': ['running']},
                {'Name': 'tag:Environment', 'Values': [ENVIRONMENT]}
            ]
        )

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instance_type = instance['InstanceType']

                # Get CPU utilization for last 7 days
                try:
                    cpu_metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/EC2',
                        MetricName='CPUUtilization',
                        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        StartTime=datetime.now() - timedelta(days=7),
                        EndTime=datetime.now(),
                        Period=3600,
                        Statistics=['Average', 'Maximum']
                    )

                    if cpu_metrics['Datapoints']:
                        avg_cpu = sum(m['Average'] for m in cpu_metrics['Datapoints']) / len(cpu_metrics['Datapoints'])
                        max_cpu = max(m['Maximum'] for m in cpu_metrics['Datapoints'])

                        # Low CPU utilization
                        if avg_cpu < 20:
                            savings = estimate_ec2_savings(instance_type, 'downsize')
                            recommendations.append(CostRecommendation(
                                resource_id=instance_id,
                                resource_type='EC2',
                                issue=f'Low CPU utilization (avg: {avg_cpu:.1f}%, max: {max_cpu:.1f}%)',
                                recommendation=f'Consider downsizing from {instance_type} or using auto-scaling',
                                potential_savings=savings
                            ))

                        # Very low utilization - candidate for termination
                        elif avg_cpu < 5 and max_cpu < 10:
                            savings = estimate_ec2_savings(instance_type, 'terminate')
                            recommendations.append(CostRecommendation(
                                resource_id=instance_id,
                                resource_type='EC2',
                                issue=f'Extremely low CPU utilization (avg: {avg_cpu:.1f}%)',
                                recommendation=f'Consider terminating unused instance {instance_type}',
                                potential_savings=savings
                            ))

                except Exception as e:
                    print(f"Error getting metrics for {instance_id}: {e}")

    except Exception as e:
        print(f"Error analyzing EC2: {e}")

    return recommendations


def analyze_rds_utilization() -> List[CostRecommendation]:
    """Find underutilized RDS instances"""
    recommendations = []

    try:
        instances = rds.describe_db_instances()

        for db in instances['DBInstances']:
            db_id = db['DBInstanceIdentifier']
            db_class = db['DBInstanceClass']

            # Get connection count
            try:
                conn_metrics = cloudwatch.get_metric_statistics(
                    Namespace='AWS/RDS',
                    MetricName='DatabaseConnections',
                    Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_id}],
                    StartTime=datetime.now() - timedelta(days=7),
                    EndTime=datetime.now(),
                    Period=3600,
                    Statistics=['Average', 'Maximum']
                )

                # Get CPU utilization
                cpu_metrics = cloudwatch.get_metric_statistics(
                    Namespace='AWS/RDS',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_id}],
                    StartTime=datetime.now() - timedelta(days=7),
                    EndTime=datetime.now(),
                    Period=3600,
                    Statistics=['Average', 'Maximum']
                )

                if conn_metrics['Datapoints'] and cpu_metrics['Datapoints']:
                    avg_conn = sum(m['Average'] for m in conn_metrics['Datapoints']) / len(conn_metrics['Datapoints'])
                    max_conn = max(m['Maximum'] for m in conn_metrics['Datapoints'])
                    avg_cpu = sum(m['Average'] for m in cpu_metrics['Datapoints']) / len(cpu_metrics['Datapoints'])

                    # Low utilization
                    if avg_cpu < 20 and max_conn < 10:
                        savings = estimate_rds_savings(db_class)
                        recommendations.append(CostRecommendation(
                            resource_id=db_id,
                            resource_type='RDS',
                            issue=f'Low utilization (CPU: {avg_cpu:.1f}%, Conn: {avg_conn:.1f})',
                            recommendation=f'Consider downsizing from {db_class}',
                            potential_savings=savings
                        ))

            except Exception as e:
                print(f"Error getting RDS metrics for {db_id}: {e}")

    except Exception as e:
        print(f"Error analyzing RDS: {e}")

    return recommendations


def analyze_ebs_volumes() -> List[CostRecommendation]:
    """Find unattached EBS volumes"""
    recommendations = []

    try:
        volumes = ec2.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )

        for volume in volumes['Volumes']:
            volume_id = volume['VolumeId']
            size_gb = volume['Size']
            created = volume['CreateTime']
            age_days = (datetime.now(created.tzinfo) - created).days

            if age_days > 7:  # Unattached for more than 7 days
                savings = size_gb * 0.10  # $0.10/GB-month for gp3
                recommendations.append(CostRecommendation(
                    resource_id=volume_id,
                    resource_type='EBS',
                    issue=f'Unattached for {age_days} days',
                    recommendation=f'Delete {size_gb}GB unattached volume',
                    potential_savings=savings
                ))

    except Exception as e:
        print(f"Error analyzing EBS: {e}")

    return recommendations


def analyze_elastic_ips() -> List[CostRecommendation]:
    """Find unused Elastic IPs"""
    recommendations = []

    try:
        addresses = ec2.describe_addresses()

        for address in addresses['Addresses']:
            if 'AssociationId' not in address:
                # Unassociated EIP
                allocation_id = address.get('AllocationId', 'N/A')
                public_ip = address.get('PublicIp', 'N/A')

                recommendations.append(CostRecommendation(
                    resource_id=allocation_id,
                    resource_type='EIP',
                    issue='Unused Elastic IP',
                    recommendation=f'Release unused EIP {public_ip}',
                    potential_savings=3.65  # $0.005/hour = ~$3.65/month
                ))

    except Exception as e:
        print(f"Error analyzing EIPs: {e}")

    return recommendations


def analyze_old_snapshots() -> List[CostRecommendation]:
    """Find old snapshots that can be deleted"""
    recommendations = []

    try:
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])

        for snapshot in snapshots['Snapshots']:
            snapshot_id = snapshot['SnapshotId']
            start_time = snapshot['StartTime']
            age_days = (datetime.now(start_time.tzinfo) - start_time).days
            size_gb = snapshot['VolumeSize']

            # Snapshots older than 90 days
            if age_days > 90:
                savings = size_gb * 0.05  # $0.05/GB-month for snapshots
                recommendations.append(CostRecommendation(
                    resource_id=snapshot_id,
                    resource_type='Snapshot',
                    issue=f'Snapshot age: {age_days} days',
                    recommendation=f'Delete old snapshot ({size_gb}GB)',
                    potential_savings=savings
                ))

    except Exception as e:
        print(f"Error analyzing snapshots: {e}")

    return recommendations


def analyze_load_balancers() -> List[CostRecommendation]:
    """Find unused load balancers"""
    recommendations = []

    try:
        load_balancers = elbv2.describe_load_balancers()

        for lb in load_balancers['LoadBalancers']:
            lb_arn = lb['LoadBalancerArn']
            lb_name = lb['LoadBalancerName']

            # Get target health
            try:
                target_groups = elbv2.describe_target_groups(
                    LoadBalancerArn=lb_arn
                )

                healthy_targets = 0
                for tg in target_groups['TargetGroups']:
                    health = elbv2.describe_target_health(
                        TargetGroupArn=tg['TargetGroupArn']
                    )
                    healthy_targets += sum(1 for t in health['TargetHealthDescriptions']
                                         if t['TargetHealth']['State'] == 'healthy')

                if healthy_targets == 0:
                    recommendations.append(CostRecommendation(
                        resource_id=lb_name,
                        resource_type='ALB',
                        issue='No healthy targets',
                        recommendation='Delete unused load balancer',
                        potential_savings=22.50  # ~$22.50/month for ALB
                    ))

            except Exception as e:
                print(f"Error checking LB targets: {e}")

    except Exception as e:
        print(f"Error analyzing load balancers: {e}")

    return recommendations


def estimate_ec2_savings(instance_type: str, action: str) -> float:
    """Estimate EC2 cost savings"""
    # Simplified pricing (actual prices vary by region)
    pricing = {
        't3.micro': 7.50,
        't3.small': 15,
        't3.medium': 30,
        't3.large': 60,
        't3.xlarge': 120,
        'm5.large': 70,
        'm5.xlarge': 140,
        'm5.2xlarge': 280,
        'r6g.large': 75,
        'r6g.xlarge': 150,
    }

    cost = pricing.get(instance_type, 100)

    if action == 'terminate':
        return cost
    elif action == 'downsize':
        return cost * 0.5  # Assume 50% savings from downsizing
    return 0


def estimate_rds_savings(db_class: str) -> float:
    """Estimate RDS cost savings"""
    # Simplified pricing
    pricing = {
        'db.t3.micro': 15,
        'db.t3.small': 30,
        'db.t3.medium': 60,
        'db.r6g.large': 150,
        'db.r6g.xlarge': 300,
    }

    cost = pricing.get(db_class, 150)
    return cost * 0.5  # Assume 50% savings from downsizing


def generate_report(recommendations: List[CostRecommendation]):
    """Generate cost optimization report"""
    total_savings = sum(r.potential_savings for r in recommendations)

    report = {
        'timestamp': datetime.now().isoformat(),
        'environment': ENVIRONMENT,
        'total_recommendations': len(recommendations),
        'potential_monthly_savings': f"${total_savings:.2f}",
        'recommendations': [r.to_dict() for r in recommendations]
    }

    # Save to file
    report_file = f'/tmp/cost-optimization-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json'
    with open(report_file, 'w') as f:
        json.dump(report, indent=2, fp=f)

    print(f"Report saved to: {report_file}")

    # Upload to S3
    try:
        s3.put_object(
            Bucket=f'smart-tutor-{ENVIRONMENT}-reports',
            Key=f'cost-optimization/{datetime.now().strftime("%Y/%m/%d")}/report.json',
            Body=json.dumps(report, indent=2),
            ContentType='application/json'
        )
        print("Report uploaded to S3")
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

    return report


def send_slack_notification(report: dict):
    """Send Slack notification with recommendations"""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        return

    import requests

    message = {
        "text": f"💰 Cost Optimization Report ({ENVIRONMENT})",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"💰 Cost Optimization Report"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Environment:*\n{ENVIRONMENT}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Potential Savings:*\n{report['potential_monthly_savings']}/month"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Recommendations:*\n{report['total_recommendations']}"
                    }
                ]
            }
        ]
    }

    # Add top 5 recommendations
    if report['recommendations']:
        top_5 = sorted(report['recommendations'],
                      key=lambda x: float(x['potential_savings_monthly'].replace('$', '')),
                      reverse=True)[:5]

        recommendations_text = "\n".join([
            f"• {r['type']}: {r['issue']} - {r['potential_savings_monthly']}"
            for r in top_5
        ])

        message['blocks'].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top Recommendations:*\n{recommendations_text}"
            }
        })

    try:
        requests.post(webhook_url, json=message, timeout=10)
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")


def main():
    print("========================================")
    print("AWS Cost Optimization Analysis")
    print("========================================")

    all_recommendations = []

    print("\n1. Analyzing EC2 instances...")
    all_recommendations.extend(analyze_ec2_utilization())

    print("2. Analyzing RDS instances...")
    all_recommendations.extend(analyze_rds_utilization())

    print("3. Analyzing EBS volumes...")
    all_recommendations.extend(analyze_ebs_volumes())

    print("4. Analyzing Elastic IPs...")
    all_recommendations.extend(analyze_elastic_ips())

    print("5. Analyzing snapshots...")
    all_recommendations.extend(analyze_old_snapshots())

    print("6. Analyzing load balancers...")
    all_recommendations.extend(analyze_load_balancers())

    print("\n========================================")
    print(f"Analysis Complete!")
    print(f"Total Recommendations: {len(all_recommendations)}")
    print("========================================\n")

    # Generate and save report
    report = generate_report(all_recommendations)

    # Print summary
    print(json.dumps(report, indent=2))

    # Send notification
    send_slack_notification(report)


if __name__ == '__main__':
    main()
