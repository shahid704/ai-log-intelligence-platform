# 🤖 AI-Powered Linux Log Intelligence & Auto-Remediation Platform

> **An event-driven cloud automation pipeline that monitors Linux server logs in real time, uses AI to diagnose failures, and automatically remediates critical incidents — all within 90 seconds, zero human touch.**

![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?style=flat&logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)
![Serverless](https://img.shields.io/badge/Architecture-Serverless-brightgreen)
![AI Powered](https://img.shields.io/badge/AI-Amazon%20Bedrock-purple)

---

## 🏗️ Architecture Overview

```
EC2 Ubuntu Server (ap-south-1)
        │  CloudWatch Agent streams /var/log/app/application.log
        ▼
CloudWatch Log Group  →  Metric Filter (ERROR / CRITICAL keywords)
        │
        ▼
CloudWatch Alarm  (threshold: ≥ 1 error in 60 seconds)
        │
        ▼
AWS Lambda — Python 3.11  (orchestration brain)
        │
        ├──▶  Amazon Bedrock (Nova Micro, us-east-1)
        │           └── Returns JSON: severity, root_cause, fix_command, summary
        │
        ├──▶  DynamoDB  LogIncidents   (permanent audit trail)
        ├──▶  SNS        LogAlerts      (email incident report)
        └──▶  SSM Run Command           (executes fix on EC2 if HIGH/CRITICAL)
                    │
                    ▼
              EC2 Instance  ← receives and runs the remediation command
```

**Design Principles:** Event-driven · Serverless · Separation of Concerns

---

## ⚡ How Fast Is It?

| Time | What Happens |
|------|-------------|
| t = 0s | EC2 writes `ERROR` or `CRITICAL` to `application.log` |
| ~60s | CloudWatch Agent streams log to AWS |
| ~61s | Metric Filter detects keyword → Alarm fires → Lambda triggered |
| ~62s | Lambda fetches 40 most recent log lines → sends to Bedrock |
| ~90s | SSM fix runs on EC2 · SNS email sent · DynamoDB record written |

---

## 🧰 AWS Services Used

| Service | What It Does Here |
|---------|-------------------|
| **EC2 t3.micro** (Ubuntu 22.04) | Linux server generating realistic application logs |
| **CloudWatch Agent + Log Group** | Streams `/var/log/app/application.log` continuously |
| **CloudWatch Metric Filter** | Converts `ERROR`/`CRITICAL` keywords → measurable metric |
| **CloudWatch Alarm** | Fires when error count ≥ 1 per 60s; triggers Lambda |
| **AWS Lambda** (Python 3.11) | Orchestrates entire response pipeline; serverless |
| **Amazon Bedrock** (Nova Micro) | AI analysis → JSON diagnosis; no 3rd-party subscription |
| **DynamoDB** (PAY_PER_REQUEST) | Stores every incident with full audit trail |
| **Amazon SNS** | Emails formatted incident report to engineer |
| **SSM Run Command** | Executes fix on EC2 — no SSH, no open ports |
| **IAM** (Least Privilege) | Scoped roles for EC2 and Lambda; no admin access |

---

## 🤖 What Bedrock Returns

Lambda sends the 40 most recent log lines with a structured prompt. Bedrock returns:

```json
{
  "severity": "HIGH",
  "root_cause": "Connection pool exhausted + OOM pressure on /var/data",
  "remediation_command": "df -h && du -sh /var/data && free -m",
  "summary": "Server experiencing OOM, connection exhaustion, and critical disk usage"
}
```

If `severity` is `HIGH` or `CRITICAL`, Lambda calls SSM Run Command to execute the fix on EC2 — automatically, without SSH or engineer involvement.

---

## 🔒 Security Design

**What this project does right:**
- IAM least-privilege on all roles — no admin access anywhere
- Zero hardcoded credentials — all auth via IAM roles attached to services
- No SSH required — SSM eliminates key management risk entirely
- Bedrock access via IAM — no API key that could accidentally leak to GitHub

**Documented gaps (learning project):**
- Lambda executes whatever command Bedrock suggests — production needs a command whitelist
- EC2 has a public IP — production instances belong in private subnets
- No VPC endpoints — production traffic should stay on the AWS private network

> ⚠️ **Disclaimer:** Auto-remediation via SSM in this project is for learning and demonstration only. In real production environments, executing commands without human approval should follow your organisation's change management and approval processes.

---

## 🚀 Implementation Steps

```
1. Created IAM Roles
   └── EC2-LogStreaming-Role (CloudWatch + SSM)
   └── Lambda-LogAnalyzer-Role (CloudWatch, Bedrock, DynamoDB, SNS, SSM)

2. Launched EC2 Instance
   └── t3.micro Ubuntu 22.04 in ap-south-1
   └── UserData bootstrapped CloudWatch Agent + log simulator on first boot

3. Created DynamoDB Table
   └── LogIncidents | PK: incident_id | SK: timestamp | PAY_PER_REQUEST

4. Created SNS Topic
   └── LogAlerts | email subscription confirmed

5. Enabled Bedrock Model Access
   └── Amazon Nova Micro enabled in us-east-1

6. Deployed Lambda Function
   └── Python 3.11 | 60s timeout | 256 MB
   └── Bedrock client → us-east-1 | all other clients → ap-south-1

7. Configured CloudWatch Monitoring
   └── Metric filter: ERROR / CRITICAL pattern → CriticalErrorCount metric
   └── Alarm: threshold ≥ 1 in 60 seconds

8. Connected Alarm to Lambda
   └── CloudWatch Logs Subscription Filter → near-real-time Lambda triggering

9. Validated End-to-End
   └── Lambda status 200 ✅ | DynamoDB record ✅ | SNS email ✅ | SSM success ✅
```

---

## 📁 Repository Structure

```
ai-log-platform/
├── lambda/
│   └── lambda_function.py       # Main Lambda handler
├── ec2-setup/
│   ├── userdata.sh               # EC2 bootstrap script
│   ├── cloudwatch-agent.json     # CloudWatch Agent config
│   └── log_simulator.py          # Realistic log generator
├── iam/
│   ├── ec2-role-policy.json      # EC2 IAM policy
│   └── lambda-role-policy.json   # Lambda IAM policy
├── docs/
│   └── architecture-diagram.png  # System architecture
└── README.md
```

---

## 🔮 Future Improvements

| Enhancement | Description |
|-------------|-------------|
| **CloudFormation** | Entire stack as one YAML template — deploy & destroy with a single command |
| **Terraform** | IaC version for multi-cloud portability |
| **Slack integration** | Incident alerts with Approve/Reject buttons before SSM runs |
| **Command whitelist** | Only pre-approved safe commands can be executed via SSM |
| **Lambda DLQ** | SQS dead-letter queue captures any failed invocations |
| **APAC Cross-Region Inference** | Keep Bedrock traffic within APAC for lower latency |
| **X-Ray tracing** | Measure pipeline latency at each stage |
| **React dashboard** | Live incident viewer via API Gateway + DynamoDB Streams |

---

## 📌 Known Limitations

This is a learning project. These gaps are intentional scope decisions, not oversights:

- Monitors one log file only (production: multiple log streams across a fleet)
- No command whitelist — Bedrock's suggested command runs as-is
- No human approval step before SSM executes
- Single EC2 instance (production: 200+ instances, same pipeline)
- No Lambda dead-letter queue for failed invocations

---

## 💬 30-Second Pitch

> *"I built a cloud automation system on AWS that monitors Linux server logs in real time, uses AI to analyse what went wrong, and automatically runs the fix — without anyone touching the server. It detects problems within 60 seconds, emails the engineer a structured AI diagnosis, and logs every incident to a database. The whole thing cost under a dollar to build and test."*

---

## 🎓 Certifications

- AWS Certified AI Practitioner
- AWS Certified Solutions Architect

---

## 📬 Connect

**LinkedIn:** [www.linkedin.com/in/shahid-sayed-311116209 ]  
**GitHub:** [ https://github.com/shahid704/ai-log-intelligence-platform/ ]

---

*Built in the Mumbai (ap-south-1) AWS region.*
