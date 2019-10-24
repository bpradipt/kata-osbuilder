%global with_debug 0

%if 0%{with_debug}
%global _find_debuginfo_dwz_opts %{nil}
%global _dwz_low_mem_die_limit 0
%else
%global debug_package %{nil}
%endif

%global katadatadir %{_datadir}/kata-containers
%global katalibexecdir %{_libexecdir}/kata-containers
%global kataosbuilderdir %{katalibexecdir}/osbuilder
%global kataagentdir %{kataosbuilderdir}/agent

%global git0 https://github.com/kata-containers/osbuilder
%global commit0 4287ba639bbec8f447295bb567636d939bcb4cfc
%global shortcommit0 %(c=%{commit0}; echo ${c:0:7})

%global git1 https://github.com/kata-containers/agent
%global commit1 8d682c45840d8bd76675879c8bbfffd9ef078838
%global shortcommit1 %(c=%{commit1}; echo ${c:0:7})


Name: kata-osbuilder
Version: 1.9.0
Release: 0.3.git%{shortcommit0}%{?dist}
License: ASL 2.0
Summary: Kata guest initrd and image build scripts
URL: %{git0}

ExcludeArch: %{arm}
# Installing requires a kernel package, which isn't available i686
ExcludeArch: %{ix86}

Source0: %{git0}/archive/%{commit0}/osbuilder-%{shortcommit0}.tar.gz
Source1: %{git1}/archive/%{commit1}/agent-%{shortcommit1}.tar.gz
Source2: fedora-kata-osbuilder.sh

# Adjust rootfs.sh to pull more pieces from the kata-agent dir,
# like systemd units. Not acceptable as is for upstream, we need
# to find a nicer solution.
Patch01: osbuilder-0001-rootfs-allow-using-systemd-units-from-AGENT_SOURCE_B.patch
# Fix symlinks in the dracut_overlay to not clobber Fedora.
# Needs to be submitted upstream
Patch02: osbuilder-0002-rootfs-Fix-systemd-sbin-init-symlinking.patch
# List of drivers needed in the initrd.
# Needs to be submitted upstream
Patch03: osbuilder-0003-dracut-Add-Fedora-virtio-kernel-modules-to-the-initr.patch

BuildRequires: git
BuildRequires: go-rpm-macros

Requires(post): qemu-img
Requires(post): dracut
Requires(post): cpio
Requires(post): bash
Requires(post): kernel
# mkfs.ext4 and tune2fs needed for the image build step
Requires(post): e2fsprogs
# gcc is used for building a little dax tool in image_builder.sh
Requires(post): gcc

# Bundled kata-agent pieces
Provides: bundled(golang(github.com/docker/docker/pkg/parsers))
Provides: bundled(golang(github.com/gogo/protobuf/gogoproto))
Provides: bundled(golang(github.com/gogo/protobuf/proto))
Provides: bundled(golang(github.com/gogo/protobuf/types))
Provides: bundled(golang(github.com/grpc-ecosystem/grpc-opentracing/go/otgrpc))
Provides: bundled(golang(github.com/hashicorp/yamux))
Provides: bundled(golang(github.com/mdlayher/vsock))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/configs))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/nsenter))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/seccomp))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/specconv))
Provides: bundled(golang(github.com/opencontainers/runc/libcontainer/utils))
Provides: bundled(golang(github.com/opencontainers/runtime-spec/specs-go))
Provides: bundled(golang(github.com/opentracing/opentracing-go))
Provides: bundled(golang(github.com/pkg/errors))
Provides: bundled(golang(github.com/sirupsen/logrus))
Provides: bundled(golang(github.com/uber/jaeger-client-go/config))
Provides: bundled(golang(github.com/vishvananda/netlink))
Provides: bundled(golang(golang.org/x/net/context))
Provides: bundled(golang(golang.org/x/sys/unix))
Provides: bundled(golang(google.golang.org/grpc))
Provides: bundled(golang(google.golang.org/grpc/codes))
Provides: bundled(golang(google.golang.org/grpc/status))


%description
%{summary}



%prep
%autosetup -Sgit -n osbuilder-%{commit0}
tar -xvf %{SOURCE1} > /dev/null


%build
# Build kata-agent
pushd agent-%{commit1}
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
mkdir -p %{buildroot}%{katadatadir}
mkdir -p %{buildroot}%{kataosbuilderdir}
mkdir -p %{buildroot}%{kataagentdir}
cp -aR rootfs-builder %{buildroot}/%{kataosbuilderdir}
cp -aR image-builder %{buildroot}/%{kataosbuilderdir}
cp -aR scripts %{buildroot}%{kataosbuilderdir}
cp -aR dracut %{buildroot}%{kataosbuilderdir}
cp -a %{_sourcedir}/fedora-kata-osbuilder.sh %{buildroot}%{kataosbuilderdir}
cp -a agent-%{commit1}/{kata-*.service,kata-*.target,kata-agent} %{buildroot}%{kataagentdir}


%post
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
%dir %{kataosbuilderdir}
%{kataosbuilderdir}/*



%changelog
* Thu Oct 24 2019 Cole Robinson <crobinso@redhat.com> - 1.9.0-0.3.git4287ba6
- Link to kernel in /usr/share/kata-containers, not /boot

* Thu Oct 10 2019 Cole Robinson <aintdiscole@gmail.com> - 1.9.0-0.2.git8d682c4
- fedora-kata-osbuilder.sh: Limit what we delete on install

* Wed Sep 18 2019 Cole Robinson <aintdiscole@gmail.com> - 1.9.0-0.1.git8d682c4
- Update to latest release 1.9.0alpha2
- Use dracut as build method for initrd + image
- Add fedora-kata-osbuilder.sh script that handls %post image building

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
