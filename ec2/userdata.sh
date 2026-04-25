#!/bin/bash
# Bootstrap: installs CloudWatch Agent and starts the log simulator
 
apt-get update -y
apt-get install -y wget
 
# Install CloudWatch Agent
wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb
 
# Write CloudWatch Agent configuration
mkdir -p /opt/aws/amazon-cloudwatch-agent/etc/
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'CWEOF'
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [{
          "file_path": "/var/log/app/application.log",
          "log_group_name": "/ec2/app/application",
          "log_stream_name": "{instance_id}"
        }]
      }
    }
  }
}
CWEOF
 
# Start CloudWatch Agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
 
# Create application log directory
mkdir -p /var/log/app
 
# Create log simulator: writes INFO logs every 30s, ERROR/CRITICAL occasionally
cat > /usr/local/bin/simulate_logs.sh << 'SIMEOF'
#!/bin/bash
LOG=/var/log/app/application.log
while true; do
  TS=$(date "+%Y-%m-%d %H:%M:%S")
  echo "$TS INFO Health check passed response_time=45ms" >> $LOG
  echo "$TS INFO Processed 120 requests" >> $LOG
  sleep 30
  R=$((RANDOM % 4))
  if [ $R -eq 0 ]; then
    echo "$TS ERROR Database connection pool exhausted active_connections=500" >> $LOG
    echo "$TS CRITICAL Out of memory killing process pid=9999" >> $LOG
    echo "$TS ERROR Disk usage critical /var/data is 96 percent full" >> $LOG
  fi
done
SIMEOF
 
chmod +x /usr/local/bin/simulate_logs.sh
nohup /usr/local/bin/simulate_logs.sh > /dev/null 2>&1 &
