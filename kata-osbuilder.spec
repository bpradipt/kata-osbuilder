%global with_debug 0

%if 0%{with_debug}
%global _find_debuginfo_dwz_opts %{nil}
%global _dwz_low_mem_die_limit 0
%else
%global debug_package %{nil}
%endif

%global katadatadir             %{_datadir}/kata-containers
%global katalibexecdir          %{_libexecdir}/kata-containers
%global kataosbuilderdir        %{katalibexecdir}/osbuilder
%global kataagentdir            %{kataosbuilderdir}/agent
%global katalocalstatecachedir  %{_localstatedir}/cache/kata-containers

%global tag                     1.10.0
%global git0    https://github.com/kata-containers/osbuilder
%global git1 https://github.com/kata-containers/agent


Name: kata-osbuilder
Version: %{tag}
Release: 5%{?dist}
License: ASL 2.0
Summary: Kata guest initrd and image build scripts
URL: %{git0}

ExcludeArch: %{arm}
# Installing requires a kernel package, which isn't available i686
ExcludeArch: %{ix86}

Source0: %{git0}/archive/%{version}/osbuilder-%{version}.tar.gz
Source1: %{git1}/archive/%{version}/agent-%{version}.tar.gz
Source2: fedora-kata-osbuilder.sh
Source3: kata-osbuilder-generate.service
Source4: agent-0001-mount-Use-virtiofs-instead-of-virtio_fs-as-typeVirti.patch
Source5: 15-dracut-fedora.conf

# Fix symlinks in the dracut_overlay to not clobber Fedora.
# Needs to be submitted upstream
Patch02: osbuilder-0002-rootfs-Don-t-overwrite-init-if-it-already-exists.patch


BuildRequires: git
BuildRequires: go-rpm-macros
BuildRequires: systemd
%{?systemd_requires}
# %check requirements
BuildRequires: kernel
BuildRequires: dracut
BuildRequires: busybox

# dracut/rootfs build deps
Requires: kernel
Requires: dracut
Requires: busybox
# image build deps
Requires: e2fsprogs
Requires: parted
# gcc is used for building a little dax tool in image_builder.sh
Requires: gcc

# Bundled kata-agent pieces
Provides: bundled(golang(github.com/docker/docker/pkg/parsers))
Provides: bundled(golang(github.com/gogo/protobuf/gogoproto))
Provides: bundled(golang(github.com/gogo/protobuf/jsonpb))
Provides: bundled(golang(github.com/gogo/protobuf/proto))
Provides: bundled(golang(github.com/gogo/protobuf/types))
Provides: bundled(golang(github.com/grpc-ecosystem/grpc-opentracing/go/otgrpc))
Provides: bundled(golang(github.com/hashicorp/yamux))
Provides: bundled(golang(github.com/mdlayher/vsock))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/cgroups))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/configs))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/nsenter))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/seccomp))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/specconv))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/utils))
Provides: bundled(golang(github.com/opencontainers/runtime-spec/specs-go))
Provides: bundled(golang(github.com/opentracing/opentracing-go))
Provides: bundled(golang(github.com/pkg/errors))
Provides: bundled(golang(github.com/sirupsen/logrus))
Provides: bundled(golang(github.com/stretchr/testify/assert))
Provides: bundled(golang(github.com/uber/jaeger-client-go/config))
Provides: bundled(golang(github.com/vishvananda/netlink))
Provides: bundled(golang(github.com/vishvananda/netns))
Provides: bundled(golang(golang.org/x/net/context))
Provides: bundled(golang(golang.org/x/sys/unix))
Provides: bundled(golang(google.golang.org/grpc))
Provides: bundled(golang(google.golang.org/grpc/codes))
Provides: bundled(golang(google.golang.org/grpc/status))


%description
%{summary}



%prep
%autosetup -Sgit -n osbuilder-%{version}
tar -xvf %{SOURCE1} > /dev/null
pushd agent-%{version}
patch -p1 < %{SOURCE4}
popd


%build
# Build kata-agent
pushd agent-%{version}
mkdir _build
pushd _build
mkdir -p src/github.com/kata-containers
ln -s $(dirs +1 -l) src/github.com/kata-containers/agent
popd

mv vendor src
export GOPATH=$(pwd)/_build:$(pwd)
%gobuild -o %{name}
make
popd



%install
# Install the whole kata agent rooted in /usr/libexec
# The whole tree is copied into the appliance by our script
mkdir -p %{buildroot}%{kataagentdir}
pushd agent-%{version}
%makeinstall DESTDIR=%{buildroot}%{kataagentdir}
popd

mkdir -p %{buildroot}%{katadatadir}
mkdir -p %{buildroot}%{kataosbuilderdir}
mkdir -p %{buildroot}%{katalocalstatecachedir}
rm rootfs-builder/.gitignore
cp -aR rootfs-builder %{buildroot}/%{kataosbuilderdir}
cp -aR image-builder %{buildroot}/%{kataosbuilderdir}
cp -aR initrd-builder %{buildroot}/%{kataosbuilderdir}
cp -aR scripts %{buildroot}%{kataosbuilderdir}
cp -aR dracut %{buildroot}%{kataosbuilderdir}
cp -a %{SOURCE5} %{buildroot}%{kataosbuilderdir}/dracut/dracut.conf.d/
cp -a %{SOURCE2} %{buildroot}%{kataosbuilderdir}
chmod +x %{buildroot}/%{kataosbuilderdir}/rootfs-builder/alpine/rootfs_lib.sh
chmod +x %{buildroot}/%{kataosbuilderdir}/rootfs-builder/suse/install-packages.sh
chmod +x %{buildroot}/%{kataosbuilderdir}/scripts/install-yq.sh
chmod +x %{buildroot}/%{kataosbuilderdir}/scripts/lib.sh

install -m 0644 -D -t %{buildroot}%{_unitdir} %{_sourcedir}/kata-osbuilder-generate.service


%check
TEST_MODE=1 %{buildroot}%{kataosbuilderdir}/fedora-kata-osbuilder.sh \
    -o %{buildroot}%{kataosbuilderdir}


%preun
%systemd_preun kata-osbuilder-generate.service
%postun
%systemd_postun kata-osbuilder-generate.service
%post
%systemd_post kata-osbuilder-generate.service

TMPOUT="$(mktemp -t kata-rpm-post-XXXXXX.log)"
echo "Creating kata appliance initrd and filesystem image..."
bash %{kataosbuilderdir}/fedora-kata-osbuilder.sh > ${TMPOUT} 2>&1
if test "$?" != "0" ; then
    echo "Building failed. See log for details: ${TMPOUT}"
    exit 1
fi



%files
%license LICENSE
%doc CODE_OF_CONDUCT.md CONTRIBUTING.md README.md
%dir %{katadatadir}
%dir %{katalibexecdir}
%dir %{kataosbuilderdir}
%{kataosbuilderdir}/*
%{kataagentdir}/usr/bin/kata-agent
%dir %{katalocalstatecachedir}
%{_unitdir}/kata-osbuilder-generate.service



%changelog
* Mon Feb 17 2020 Cole Robinson <aintdiscole@gmail.com> - 1.10.0-5
- Add runtime busybox dep, for dracut debug modules

* Sat Feb 15 2020 Cole Robinson <aintdiscole@gmail.com> - 1.10.0-4
- Fixes for virtio-fs
- Add modules to aid debugging appliance initrd/image

* Fri Feb 14 2020 Cole Robinson <aintdiscole@gmail.com> - 1.10.0-3
- Add kata-osbuilder-generate.service

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.10.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Tue Jan 21 2020 Christophe de Dinechin <dinechin@redhat.com> - 1.10.0-1
- Update to release 1.10.0

* Fri Jan 17 2020 Christophe de Dinechin <dinechin@redhat.com> - 1.9.3-1
- Update to 1.9.3 (No change upstream)

* Fri Jan 17 2020 Christophe de Dinechin <dinechin@redhat.com> - 1.9.2-1
- Update to 1.9.2 (No change upstream)

* Fri Jan 17 2020 Fabiano Fidêncio <fidencio@redhat.com> - 1.9.1-2
- Remove unneeded nsdax binary file - rhbz#1792216
- Install images in /var/cache instead of /usr/libexec - rhbz#1792216

* Fri Nov 29 2019 Christophe de Dinechin <dinechin@redhat.com> - 1.9.1-1
- Udpate to 1.9.1

* Tue Nov 19 2019 Christophe de Dinechin <dinechin@redhat.com> - 1.9.0-4
- Address remaining warnigns reported by rpmlint / rpmgrill, see bz1773629

* Tue Nov 19 2019 Christophe de Dinechin <dinechin@redhat.com> - 1.9.0-3
- Address various errors and warnings reported by rpmlint / rpmgrill:
+ Add rpmlintrc filter to address bogus spelling erorrs (initrd -> trinity)
+ Add rpmlintrc filter to remove golang macros warnings (no version number)
+ Rmove percent sign in changelog
+ Use SOURCE2 instead of _sourcedir to avoid rpmlint error
+ Add missing golang packages in the provides list (from golist)
+ Fix permission for fedora-kata-osbuilder.sh

* Thu Nov 14 2019 Christophe de Dinechin <dinechin@redhat.com> - 1.9.0-2
- Build from tag instead of commit

* Thu Nov 14 2019 Christophe de Dinechin <dinechin@redhat.com> - 1.9.0-1
- Update to release 1.9.0

* Thu Oct 24 2019 Cole Robinson <crobinso@redhat.com> - 1.9.0-0.3.git4287ba6
- Link to kernel in /usr/share/kata-containers, not /boot

* Thu Oct 10 2019 Cole Robinson <aintdiscole@gmail.com> - 1.9.0-0.2.git8d682c4
- fedora-kata-osbuilder.sh: Limit what we delete on install

* Wed Sep 18 2019 Cole Robinson <aintdiscole@gmail.com> - 1.9.0-0.1.git8d682c4
- Update to latest release 1.9.0alpha2
- Use dracut as build method for initrd + image
- Add fedora-kata-osbuilder.sh script that handles {percent}post image building

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.1-4.git72c5f6a
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.1-3.git72c5f6a
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Dec 13 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.1-2.git72c5f6a
- enable all arches

* Thu Dec 13 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.1-1.git72c5f6a
- Resolves: #1590414 - first build for Fedora
- bump to v1.4.1

* Mon Nov 26 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.0-4.git39e6aa4
- update summary and description

* Mon Nov 26 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.0-3.git39e6aa4
- install license and docs

* Fri Nov 23 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.0-2.git39e6aa4
- use qemu-img

* Fri Nov 23 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.4.0-1.git39e6aa4
- bump to v1.4.0
- built commit 39e6aa4

* Sun Nov 11 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.0.0-1.git37d1824
- bump to 1.3.1
- built commit 37d1824

* Thu Jun 28 2018 Lokesh Mandvekar <lsm5@fedoraproject.org> - 1.0.0-1.gitac0c290
- initial build
