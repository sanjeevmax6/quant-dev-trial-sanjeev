variable "public_key_path" {
  description = "Path to your SSH public key"
  default     = "~/.ssh/id_rsa.pub"
}

variable "csv_file_path" {
  description = "Path to l1_day.csv"
  default     = "./l1_day.csv"
}