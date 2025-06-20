
# Smart Order Router – EC2 Deployed Backtester

## Directory Structure

The following structure guides the full backtesting and deployment setup:

```
.
├── allocator.py
├── allocator_pseudocode.txt
├── backtest.py
├── docker-compose.yml
├── greedy_allocator.py
├── kafka_producer.py
├── l1_day.csv               # Not committed. Must be placed manually.
├── requirements.txt
├── result.json
├── README.md
├── deployment/
│   ├── bootstrap.sh
│   ├── main.tf
│   ├── outputs.tf
│   ├── variables.tf
│   └── terraform.tfstate / .backup
```
---

## Architecture Overview

1. **Kafka & Zookeeper Setup**:  
   Docker Compose provisions two containers (`confluentinc/cp-zookeeper` and `cp-kafka`) that run locally or inside the EC2 instances.

2. **Python Environment & Allocation Logic**:
   - `requirements.txt` installs all dependencies (standard lib + pandas + numpy only)
   - `allocator.py` implements the Cont-Kukanov recursive optimizer
   - `greedy_allocator.py` used for simpler SOR comparison (Tried it out in a motive to simulate real world analytics, by referring to the Cont Kukanov paper)

3. **Kafka Producer**:
   - Reads `l1_day.csv` between 13:36:32 and 13:45:14 UTC
   - Pushes timestamped venue data into the Kafka topic `mock_l1_stream`
   - `time.sleep()` simulates real-time stream pacing

4. **Backtesting**:
   - `backtest.py` ingests Kafka stream and reconstructs snapshots
   - For each snapshot: optimizes allocation, executes fills, applies penalties
   - Includes grid search over λ_over, λ_under, θ_queue

---

## EC2 + Terraform Setup (Automated)

### Prerequisites

- Terraform ≥ 1.0
- AWS CLI configured (`aws configure`)
- SSH key pair available (see below)
- Place `l1_day.csv` in `deployment/` directory manually before proceeding.

### Generate SSH Key (if not existing)

```bash
ls ~/.ssh/id_rsa.pub || ssh-keygen -t rsa -b 4096
```

---

### 🛠️ Deployment Steps

1. **Navigate to Terraform Directory**
   ```bash
   cd deployment
   ```

2. **Initialize Terraform**
   ```bash
   terraform init
   ```

3. **(Optional) Review Plan**
   ```bash
   terraform plan
   ```

4. **Apply and Create EC2**
   ```bash
   terraform apply
   ```

   - Region: `us-east-1`
   - Type: `t3.micro`
   - Bootstraps: Docker, Python, pip, requirements
   - Also uploads `l1_day.csv` into `~/quant-dev-trial-sanjeev/`

---

## SSH into EC2 (Please waiit for atleast ~5 min [Bootstrapping takes time, and interferring could cause unnecessary errors])

```bash
ssh -i ~/.ssh/id_rsa ubuntu@<EC2_PUBLIC_IP>
```

> Wait 3–5 minutes after `terraform apply` to let bootstrapping complete.

---

## Run the Full Pipeline

1. **Navigate into project folder**  
   ```bash
   cd ~/quant-dev-trial-sanjeev
   ```

2. **Start Kafka & Zookeeper**
   ```bash
   docker compose up -d
   ```

3. **Run Kafka Producer**
   ```bash
   python3 kafka_producer.py
   ```

4. **Run Backtest and Output Results**
   ```bash
   python3 backtest.py
   ```
---

## Results

```json
{
  "best_parameters": {
    "lambda_over": 0.1,
    "lambda_under": 0.1,
    "theta_queue": 0.05
  },
  "optimized": {
    "total_cash": 1113705.0,
    "avg_fill_px": 222.741
  },
  "baselines": {
    "best_ask": {
      "total_cash": 1113649.9,
      "avg_fill_px": 222.73
    },
    "twap": {
      "total_cash": 1115249.23,
      "avg_fill_px": 223.0498
    },
    "vwap": {
      "total_cash": 1112846.2,
      "avg_fill_px": 222.7474
    }
  },
  "savings_vs_baselines_bps": {
    "best_ask": -0.49,
    "twap": 13.85,
    "vwap": -7.72
  }
}
```

---

---

## Alternate Deployment (Without Terraform)

If you'd prefer or need to deploy manually without using Terraform, follow these steps:

### Step 1: Launch EC2 Instance

- Log in to your AWS Console.
- Navigate to **EC2** and launch a new instance.
- Recommended instance type: `t3.micro` or `t4g.micro` (ARM-compatible).
- Choose an Ubuntu 20.04 or 22.04 AMI.
- Make sure to allow inbound **SSH (port 22)** and **Docker/Kafka ports (e.g. 9092)** in the security group.
- Add your key pair or create one to allow SSH access.

### Step 2: SSH into EC2

```bash
ssh -i /path/to/your/key.pem ubuntu@<your-ec2-public-ip>
```
Replace `<your-ec2-public-ip>` with your actual EC2 public IP.

---

### Step 3: Clone the Repository

```bash
sudo apt update && sudo apt install git -y
git clone https://github.com/<your-username>/quant-dev-trial-sanjeev.git
cd quant-dev-trial-sanjeev
```

---

### Step 4: Install requirements and packages

```bash
cd quant-dev-trial-sanjeev/deployment
chmod +x bootstrap.sh
bash bootstrap.sh
```

---

### Step 5: Transfer `l1_day.csv` to EC2

> Use `scp` to transfer it directly.

From your local machine:

```bash
scp -i /path/to/your/key.pem ./l1_day.csv ubuntu@<your-ec2-public-ip>:~/quant-dev-trial-sanjeev/
```

---

### Step 6: Start Docker

Start Kafka + Zookeeper containers:

```bash
docker compose up -d
```

---

### Step 6: Run the Pipeline

1. Start the Kafka producer:
```bash
python3 kafka_producer.py
```

2. Then run the backtest:
```bash
python3 backtest.py
```

---

## Cleanup
Navigate to your local terminal's repo and do

```bash
terraform destroy
```

This will tear down all the resources gracefully


## Video Walkthrough

> https://drive.google.com/file/d/1XJwavIivf9Izssaqtd0zfXDqKpJcLiCK/view?usp=sharing

Quick note: I forgot to mention this in the video — since the dataset shouldn’t be public in the repo, I used aws provisioner to securely transfer the script from my local deployment/ directory to the EC2 instance's root directory. Then, inside the instance, the bootstrap.sh script copies it to the appropriate working directory during setup.


