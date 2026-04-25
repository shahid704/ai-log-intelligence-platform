import boto3
import json
import uuid
from datetime import datetime
 
BEDROCK_REGION = "us-east-1"   # Bedrock: Nova Micro available here
APP_REGION     = "ap-south-1"  # All other services in Mumbai
TABLE_NAME     = "LogIncidents"
SNS_ARN        = "arn:aws:sns:ap-south-1:242836824895:LogAlerts"
 
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
logs    = boto3.client("logs",            region_name=APP_REGION)
dynamo  = boto3.resource("dynamodb",      region_name=APP_REGION)
sns_c   = boto3.client("sns",             region_name=APP_REGION)
ssm     = boto3.client("ssm",             region_name=APP_REGION)
 
def get_recent_logs(log_group, log_stream, num_lines=40):
    try:
        resp = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            limit=num_lines,
            startFromHead=False
        )
        lines = [e["message"] for e in resp["events"]]
        return "\n".join(lines) if lines else "No log entries found."
    except Exception as e:
        return "Could not fetch logs: " + str(e)
 
def analyze_with_bedrock(log_text):
    prompt = (
        "You are a senior Linux SRE. Analyze these logs.\n"
        "Respond ONLY in this exact JSON format (no extra text, no markdown fences):\n"
        "{\n"
        '  "severity": "HIGH",\n'
        '  "root_cause": "brief explanation",\n'
        '  "remediation_command": "safe single bash command",\n'
        '  "summary": "one line summary"\n'
        "}\n\n"
        "LOGS:\n" + log_text
    )
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 400, "temperature": 0}
    })
    resp   = bedrock.invoke_model(modelId="amazon.nova-micro-v1:0", body=body)
    result = json.loads(resp["body"].read())
    text   = result["output"]["message"]["content"][0]["text"].strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1: text = parts[1]
        if text.lower().startswith("json"): text = text[4:].strip()
    return json.loads(text)
 
def lambda_handler(event, context):
    instance_id = event.get("instance_id", "i-test000")
    log_group   = event.get("log_group",   "/ec2/app/application")
    log_stream  = event.get("log_stream",   instance_id)
    log_text = get_recent_logs(log_group, log_stream)
 
    try:
        analysis = analyze_with_bedrock(log_text)
    except Exception as e:
        analysis = {
            "severity": "UNKNOWN",
            "root_cause": "AI analysis failed: " + str(e),
            "remediation_command": "manual review required",
            "summary": "Bedrock analysis error"
        }
 
    incident_id = str(uuid.uuid4())[:8]
    remediated  = False
    cmd_id      = "N/A"
 
    if analysis.get("severity") in ["HIGH", "CRITICAL"]:
        try:
            r = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [analysis["remediation_command"]]}
            )
            cmd_id    = r["Command"]["CommandId"]
            remediated = True
        except Exception as e:
            cmd_id = "SSM failed: " + str(e)
 
    dynamo.Table(TABLE_NAME).put_item(Item={
        "incident_id":          incident_id,
        "timestamp":            datetime.utcnow().isoformat(),
        "instance_id":          instance_id,
        "severity":             analysis.get("severity", "UNKNOWN"),
        "root_cause":           analysis.get("root_cause", ""),
        "summary":              analysis.get("summary", ""),
        "remediation_command":  analysis.get("remediation_command", ""),
        "remediated":           str(remediated),
        "ssm_command_id":       cmd_id
    })
 
    msg = (
        "AI INCIDENT REPORT\n"
        "ID       : " + incident_id + "\n"
        "Instance : " + instance_id + "\n"
        "Severity : " + str(analysis.get("severity")) + "\n"
        "Summary  : " + str(analysis.get("summary")) + "\n"
        "Cause    : " + str(analysis.get("root_cause")) + "\n"
        "Fix      : " + str(analysis.get("remediation_command")) + "\n"
        "Applied  : " + str(remediated)
    )
    sns_c.publish(TopicArn=SNS_ARN, Subject="AI Log Alert", Message=msg)
    return {"statusCode": 200, "body": json.dumps(analysis)}
