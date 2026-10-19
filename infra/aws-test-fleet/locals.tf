locals {
  # Named host sets. Keys carry the OS, release, and architecture, so a host
  # keeps its name, and its state, when it appears in more than one set.
  fleet_sets = {
    lts = {
      ubuntu-2604-amd64 = { os = "ubuntu", release = "26.04", architecture = "amd64" }
      ubuntu-2604-arm64 = { os = "ubuntu", release = "26.04", architecture = "arm64" }
    }
    full = {
      ubuntu-2404-amd64 = { os = "ubuntu", release = "24.04", architecture = "amd64" }
      ubuntu-2404-arm64 = { os = "ubuntu", release = "24.04", architecture = "arm64" }
      ubuntu-2604-amd64 = { os = "ubuntu", release = "26.04", architecture = "amd64" }
      ubuntu-2604-arm64 = { os = "ubuntu", release = "26.04", architecture = "arm64" }
      ubuntu-2610-amd64 = { os = "ubuntu", release = "26.10", architecture = "amd64" }
      ubuntu-2610-arm64 = { os = "ubuntu", release = "26.10", architecture = "arm64" }
      # Arch Linux publishes no arm64 image, so it has no arm64 mirror.
      arch-amd64       = { os = "arch", release = "rolling", architecture = "amd64" }
      alpine-324-amd64 = { os = "alpine", release = "3.24", architecture = "amd64" }
      alpine-324-arm64 = { os = "alpine", release = "3.24", architecture = "arm64" }
    }
  }

  # Used when a custom hosts entry leaves release unset.
  default_release = {
    ubuntu = "26.04"
    alpine = "3.24"
    arch   = "rolling"
  }

  # A custom map replaces the named set. Both shapes normalize to one object
  # type, so the module call reads a single map.
  selected_hosts = var.hosts != null ? {
    for key, host in var.hosts : key => {
      os            = host.os
      architecture  = host.architecture
      release       = coalesce(host.release, local.default_release[host.os])
      instance_type = coalesce(host.instance_type, var.instance_types[host.architecture])
    }
    } : {
    for key, host in local.fleet_sets[var.fleet_set] : key => {
      os            = host.os
      architecture  = host.architecture
      release       = host.release
      instance_type = var.instance_types[host.architecture]
    }
  }
}
