variable "image_tag" {
  type    = string
  default = "20260501.1"
}

variable "template_variant" {
  type    = string
  default = "pretty"

  validation {
    condition     = contains(["pretty", "messy"], var.template_variant)
    error_message = "template_variant must be one of: pretty, messy."
  }
}
