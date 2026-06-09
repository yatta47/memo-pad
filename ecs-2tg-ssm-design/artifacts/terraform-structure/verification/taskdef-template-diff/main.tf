locals {
  aws_region_name    = "ap-northeast-1"
  ecr_repository_url = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/aservice"
  container_name     = "aservice"
  container_port     = 8080
  log_group          = "/ecs/env02/aservice"
  main_image_uri     = "${local.ecr_repository_url}:${var.image_tag}"

  direct_container_definition = [
    {
      name      = local.container_name
      image     = local.main_image_uri
      essential = true
      portMappings = [
        {
          containerPort = local.container_port
          hostPort      = local.container_port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = local.log_group
          awslogs-region        = local.aws_region_name
          awslogs-stream-prefix = "main"
        }
      }
    }
  ]

  direct_container_definitions = jsonencode(local.direct_container_definition)

  template_vars = {
    container_name  = local.container_name
    image_uri       = local.main_image_uri
    container_port  = local.container_port
    log_group       = local.log_group
    aws_region_name = local.aws_region_name
  }

  template_files = {
    pretty = "${path.module}/taskdef.pretty.json.tftpl"
    messy  = "${path.module}/taskdef.messy.json.tftpl"
  }

  selected_template_raw = templatefile(local.template_files[var.template_variant], local.template_vars)

  # Normalize template JSON before using it as container_definitions.
  container_definitions = jsonencode(jsondecode(local.selected_template_raw))
}

resource "terraform_data" "render_probe" {
  input = {
    image_tag             = var.image_tag
    container_definitions = local.container_definitions
  }
}
