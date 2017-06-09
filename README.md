# nmos-discovery-registration-ri

Reference implementation of the AMWA NMOS [IS-04 Discovery and Registration Specification][is-04].

# Introduction

The [Networked Media Open Specifications (NMOS)][nmos] is a growing family of specifications for professional networked media, created by the [Advanced Media Workflow Association (AMWA)][amwa]. NMOS specifications are made available [(on GitHub)][amwa-github] to support the development of products and services which work within an open industry framework.

This repository provides a reference implementation of [IS-04][is-04], the AMWA NMOS Discovery and Registration Specification. This specifies HTTP/JSON APIs for registering and querying information about the resources in a networked media system.

> For an introduction of the NMOS specifications, see the technical overview https://github.com/AMWA-TV/nmos, and then read the more detailed documentation in the IS-04 specification.


# This repository
This repository contains debianized NMOS API source and also a Vagrant file (plus provisioning scripts) to start a two VM NMOS cluster (one machine hosting Registration and Query APIs (hostname regquery), the other being an NMOS Node (hostname node))

Repository structure:

```
mdns-bridge/
    Implementation of a read only zeroconf to HTTP bridge (specifically looking for NMOS services).
    This is used by the Node API to find Registration APIs.
nmos-common/
    Debianised shared python modules across various APIs.
nmos-node/
    Debianised NMOS Node API implementation (includes a mock data provider)
nmos-query/
    Debianised NMOS Query API implementation
nmos-registration/
    Debianised NMOS Registration API implementation
reverse-proxy/
    A reverse proxy implementation to present the above microservices on port 80 paths using apache2.
vagrant/
    Vagrant file and provisioning scripts
```

# Prerequisites

For the best experience:
- Use a host machine running Ubuntu Linux (tested on 16.04 and 14.04).
- Install [Vagrant][vagrant-install] using a [VirtualBox][vagrant-virtualbox] as a provider.

First install debian packaging dependencies on the host:
```
sudo apt-get update
sudo apt-get install python-all debhelper pbuilder dh-python apache2-dev devscripts
```

[Optionally] Install Vagrant proxyconf plugin if you want to easily pass host machine proxy configuration to the guest machines:
```
vagrant plugin install vagrant-proxyconf
```

[Optionally] Set environment http proxy variables (these will be passed to Vagrant VMs for use by apt and pip if Vagrant proxyconf plugin is installed):
```
export http_proxy=http://<path-to-your-proxy:proxy-port>
export https_proxy=https://<path-to-your-proxy:proxy-port>
```

# Start

Now make the debian packages from source:
```
rnmos-discovery-registration-ri/$ make deb
```

Finally, bring up the VMs:
```
nmos-discovery-registration-ri/$ vagrant up
```

This will start two Ubuntu 16.04 VMs (named 'regquery' and 'node') and run provisioning scripts to install external python dependencies and the previously built debian packages.

By default the VMs are configured share a private network with no external port forwarding. You can SSH to either of the instances, e.g.:
```
vagrant ssh reqquery
```
Once SSHd simple cURL commands will verify the operation of the APIs/registration and discovery, e.g.:
```
curl --noproxy localhost localhost/x-nmos/query/v1.1/nodes/
```
Should show a single Node registered.



[comment]: <> (References/Links)

  [is-04]: https://github.com/AMWA-TV/nmos-discovery-registration "IS-04 Discovery and Registration Specification"

  [nmos]: http://nmos.tv/ "NMOS"

  [amwa]: http://amwa.tv/ "AMWA"

  [amwa-github]: https://github.com/AMWA-TV "AMWA-TV GitHub"

  [is-04]: https://github.com/AMWA-TV/nmos-discovery-registration "IS-04"

  [vagrant-install]: https://www.vagrantup.com/docs/installation/ "Vagrant Installation"
   [vagrant-virtualbox]: https://www.vagrantup.com/docs/virtualbox/ "Vagrant VirtualBox"
