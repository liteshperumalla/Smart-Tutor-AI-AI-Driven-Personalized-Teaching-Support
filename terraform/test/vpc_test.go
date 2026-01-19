package test

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/aws"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestVPCModule(t *testing.T) {
	t.Parallel()

	// AWS region for testing
	awsRegion := "us-east-1"

	terraformOptions := &terraform.Options{
		// Path to Terraform module
		TerraformDir: "../modules/vpc",

		// Variables to pass to Terraform
		Vars: map[string]interface{}{
			"vpc_cidr":      "10.0.0.0/16",
			"environment":   "test",
			"project_name":  "smart-tutor-test",
			"aws_region":    awsRegion,
			"public_subnet_cidrs": []string{
				"10.0.1.0/24",
				"10.0.2.0/24",
				"10.0.3.0/24",
			},
			"private_subnet_cidrs": []string{
				"10.0.11.0/24",
				"10.0.12.0/24",
				"10.0.13.0/24",
			},
			"availability_zones": []string{
				"us-east-1a",
				"us-east-1b",
				"us-east-1c",
			},
		},

		// Retry settings
		MaxRetries:         3,
		TimeBetweenRetries: 5,
	}

	// Clean up resources at the end
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// Test 1: Verify VPC ID is not empty
	vpcID := terraform.Output(t, terraformOptions, "vpc_id")
	assert.NotEmpty(t, vpcID, "VPC ID should not be empty")

	// Test 2: Verify VPC exists in AWS
	vpc := aws.GetVpcById(t, vpcID, awsRegion)
	assert.NotNil(t, vpc, "VPC should exist in AWS")
	assert.Equal(t, "10.0.0.0/16", vpc.CidrBlock, "VPC CIDR should match")

	// Test 3: Verify public subnets were created
	publicSubnetIDs := terraform.OutputList(t, terraformOptions, "public_subnet_ids")
	assert.Equal(t, 3, len(publicSubnetIDs), "Should have 3 public subnets")

	// Test 4: Verify private subnets were created
	privateSubnetIDs := terraform.OutputList(t, terraformOptions, "private_subnet_ids")
	assert.Equal(t, 3, len(privateSubnetIDs), "Should have 3 private subnets")

	// Test 5: Verify Internet Gateway exists
	igwID := terraform.Output(t, terraformOptions, "internet_gateway_id")
	assert.NotEmpty(t, igwID, "Internet Gateway ID should not be empty")

	// Test 6: Verify NAT Gateways created
	natGatewayIDs := terraform.OutputList(t, terraformOptions, "nat_gateway_ids")
	assert.True(t, len(natGatewayIDs) >= 1, "At least one NAT Gateway should exist")

	// Test 7: Verify public subnets are actually public
	for _, subnetID := range publicSubnetIDs {
		subnet := aws.GetSubnetById(t, subnetID, awsRegion)
		assert.True(t, subnet.MapPublicIpOnLaunch, "Public subnet should auto-assign public IPs")
	}

	// Test 8: Verify tags
	tags := vpc.Tags
	assert.Contains(t, tags, "Environment", "VPC should have Environment tag")
	assert.Equal(t, "test", tags["Environment"], "Environment tag should be 'test'")
	assert.Contains(t, tags, "ManagedBy", "VPC should have ManagedBy tag")
	assert.Equal(t, "Terraform", tags["ManagedBy"], "ManagedBy should be 'Terraform'")
}

func TestVPCModuleWithCustomCIDR(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	terraformOptions := &terraform.Options{
		TerraformDir: "../modules/vpc",
		Vars: map[string]interface{}{
			"vpc_cidr":     "172.16.0.0/16",
			"environment":  "test-custom",
			"project_name": "smart-tutor-test",
			"aws_region":   awsRegion,
			"public_subnet_cidrs": []string{
				"172.16.1.0/24",
				"172.16.2.0/24",
			},
			"private_subnet_cidrs": []string{
				"172.16.11.0/24",
				"172.16.12.0/24",
			},
			"availability_zones": []string{
				"us-east-1a",
				"us-east-1b",
			},
		},
		MaxRetries:         3,
		TimeBetweenRetries: 5,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.InitAndApply(t, terraformOptions)

	// Verify custom CIDR was used
	vpcID := terraform.Output(t, terraformOptions, "vpc_id")
	vpc := aws.GetVpcById(t, vpcID, awsRegion)
	assert.Equal(t, "172.16.0.0/16", vpc.CidrBlock, "Custom VPC CIDR should be used")
}

func TestVPCModuleValidation(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	// Test invalid CIDR block
	terraformOptions := &terraform.Options{
		TerraformDir: "../modules/vpc",
		Vars: map[string]interface{}{
			"vpc_cidr":     "invalid-cidr",
			"environment":  "test",
			"project_name": "smart-tutor-test",
			"aws_region":   awsRegion,
		},
		MaxRetries:         3,
		TimeBetweenRetries: 5,
	}

	// This should fail during plan/apply
	_, err := terraform.InitAndPlanE(t, terraformOptions)
	assert.Error(t, err, "Invalid CIDR should cause error")
}
