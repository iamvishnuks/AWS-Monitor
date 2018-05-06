from flask import render_template,Flask,jsonify
import boto3
import datetime

app = Flask(__name__)

region = 'us-east-1'
con = boto3.client('ec2', region_name=region)

cw = boto3.client('cloudwatch', region_name=region)


def get_elb_info():
    client = boto3.client('elbv2', region_name=region)
    elb_response = client.describe_load_balancers()
    elbs = []
    elb_data={}
    for elb in elb_response['LoadBalancers']:
        elb_data['name'] = elb['LoadBalancerName']
        elb_data['dns'] = elb['DNSName']
        elb_data['state'] = elb['State']['Code']
        elb_data['type'] = elb['Type']
        elbs.append(elb_data)
    return elbs


def get_rds_info():
    client = boto3.client('rds', region_name=region)
    rds_response = client.describe_db_instances()
    rds_data = {}
    rds = []
    if len(rds_response['DBInstances']) > 0:
        for i in rds_response['DBInstances']:
            rds_data['engine'] = i['Engine']
            rds_data['storage'] = i['AllocatedStorage']
            rds_data['status'] = i['DBInstanceStatus']
            rds_data['name'] = i['DBInstanceIdentifier']
            rds.append(rds_data)
        return rds
    else:
        return rds

def get_all_buckets():
    client = boto3.client('s3', region_name=region)
    buckets = client.list_buckets()
    buckets = buckets['Buckets']
    b=[]
    for i in buckets:
        b.append(i['Name'])
    return b


@app.route('/s3')
def list_all_buckets():
    return jsonify({'buckets':get_all_buckets()})


@app.route('/rds')
def get_rds_details():
    return jsonify({'rds':get_rds_info()})


@app.route('/elb')
def get_elbs_details():
    return jsonify({'elbs':get_elb_info()})


@app.route('/')
@app.route('/index')
def index():
    #EC2 details
    instances = con.describe_instances()
    instance_count = len(instances['Reservations'])
    stopped = 0
    running = 0
    for i in instances['Reservations']:
        if i['Instances'][0]['State']['Name'] == 'stopped':
            stopped = stopped + 1
        elif i['Instances'][0]['State']['Name'] == 'running':
            running = running + 1
    instance_count = len(instances['Reservations'])
    #S3 details
    s3 = boto3.resource('s3',region_name=region)
    bucket_list = [bucket.name for bucket in s3.buckets.all()]
    s3_count = len(bucket_list)
    elb_count = len(get_elb_info())
    rds_count = len(get_rds_info())
    return render_template('index.html', title='Home', instance_count=str(instance_count), stopped=stopped, running=running,
                           s3_count=s3_count, elb_count=elb_count, rds_count=rds_count)


global gcpu_usage
gcpu_usage = 0


@app.route('/get_instances')
def get_instances():
    global gcpu_usage
    con = boto3.client('ec2', region_name=region)
    instances = con.describe_instances()
    instances = instances['Reservations']
    for i in instances:
        instance_id=i['Instances'][0]['InstanceId']
        cpu_usage = cw.get_metric_statistics(
            Period=300,
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=0.054),
            EndTime=datetime.datetime.utcnow(),
            MetricName='CPUUtilization',
            Namespace='AWS/EC2',
            Statistics=['Average'],
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
        )
        if len(cpu_usage['Datapoints']) > 0:
            cpu_usage = cpu_usage['Datapoints'][0]['Average']
            gcpu_usage = cpu_usage
        else:
            cpu_usage = gcpu_usage
        i['Instances'][0]['CPU_data'] = cpu_usage
        disk_read = cw.get_metric_statistics(
            Period=300,
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=.125),
            EndTime=datetime.datetime.utcnow(),
            MetricName='DiskReadOps',
            Namespace='AWS/EC2',
            Statistics=['Average'],
            Dimensions=[{'Name':'InstanceId', 'Value':instance_id}]
        )
        if len(disk_read['Datapoints']) > 0:
            i['Instances'][0]['DiskReads'] = disk_read['Datapoints'][0]['Average']
        else:
            i['Instances'][0]['DiskReads'] = 0
    return jsonify(instances)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
