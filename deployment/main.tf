provider "aws" {
  region = "us-east-1"
}

resource "aws_key_pair" "deployer" {
  key_name   = "blockhouse-key"
  public_key = file(var.public_key_path)
}

resource "aws_security_group" "quant_sg" {
  name        = "quant-sg"
  description = "Allow SSH and Kafka"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "quant_instance" {
  ami                    = "ami-053b0d53c279acc90" # Ubuntu 20.04 (us-east-1)
  instance_type          = "t3.micro"
  key_name               = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.quant_sg.id]

  user_data = file("${path.module}/bootstrap.sh")

  tags = {
    Name = "QuantSORInstance"
  }
}

# Upload the CSV file
resource "null_resource" "upload_csv" {
  provisioner "file" {
    source      = var.csv_file_path
    destination = "/home/ubuntu/l1_day.csv"

    connection {
      type        = "ssh"
      user        = "ubuntu"
      host        = aws_instance.quant_instance.public_ip
      private_key = file(var.private_key_path)
    }
  }

  depends_on = [aws_instance.quant_instance]
}

