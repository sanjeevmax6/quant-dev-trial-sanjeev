variable "public_key_path" {
  description = "Path to your SSH public key"
  default     = "~/.ssh/id_rsa.pub"
}

variable "csv_file_path" {
  description = "Path to the l1_day.csv file"
  default     = "./l1_day.csv"
}