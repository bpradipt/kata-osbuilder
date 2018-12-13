%global with_debug 0

%if 0%{with_debug}
%global _find_debuginfo_dwz_opts %{nil}
%global _dwz_low_mem_die_limit 0
%else
%global debug_package %{nil}
%endif

%global katadir %{_datadir}/kata-containers
%global katalibexecdir %{_libexecdir}/kata-containers

%global git0 https://github.com/kata-containers/osbuilder
%global commit0 72c5f6a223964e6c3dae220bb6cd08bd94be8c8b
%global shortcommit0 %(c=%{commit0}; echo ${c:0:7})

Name: kata-osbuilder
Version: 1.4.1
Release: 2.git%{shortcommit0}%{?dist}
License: ASL 2.0
Summary: Guest OS building scripts
URL: %{git0}
Source0: %{git0}/archive/%{commit0}/osbuilder-%{shortcommit0}.tar.gz
BuildRequires: git
BuildRequires: %{?go_compiler:compiler(go-compiler)}%{!?go_compiler:golang}
Requires(post): %{?go_compiler:compiler(go-compiler)}%{!?go_compiler:golang}
Requires(post): go-srpm-macros
Requires(post): qemu-img

%description
%{summary}

%prep
%autosetup -Sgit -n osbuilder-%{commit0}

%build

%install
install -dp %{buildroot}%{katadir}
install -dp %{buildroot}%{katalibexecdir}/{image-builder,initrd-builder,rootfs-builder,scripts}
install -p -m 755 rootfs-builder/rootfs.sh %{buildroot}%{katalibexecdir}/rootfs-builder/kata-rootfs_builder
install -p -m 644 rootfs-builder/versions.txt %{buildroot}%{katalibexecdir}/rootfs-builder/versions.txt
install -p -m 755 image-builder/image_builder.sh %{buildroot}%{katalibexecdir}/image-builder/kata-image_builder
install -p -m 755 initrd-builder/initrd_builder.sh %{buildroot}%{katalibexecdir}/initrd-builder/kata-initrd_builder
install -p -m 755 scripts/lib.sh %{buildroot}%{katalibexecdir}/scripts/lib.sh

for distro in alpine centos clearlinux euleros fedora
do
    install -dp %{buildroot}%{katalibexecdir}/rootfs-builder/$distro
    install -p -m 644 rootfs-builder/$distro/config.sh %{buildroot}%{katalibexecdir}/rootfs-builder/$distro
done

%post
echo "Creating Fedora image..."
GOPATH=%{gopath} OS_VERSION=%{?fedora} %{katalibexecdir}/rootfs-builder/kata-rootfs_builder fedora
GOPATH=%{gopath} %{katalibexecdir}/image-builder/kata-image_builder %{katalibexecdir}/rootfs-builder/rootfs-Fedora
GOPATH=%{gopath} %{katalibexecdir}/initrd-builder/kata-initrd_builder %{katalibexecdir}/rootfs-builder/rootfs-Fedora
mv /kata-* %{katadir}
rm -rf %{katalibexecdir}/rootfs-builder/rootfs-Fedora

#define license tag if not already defined
%{!?_licensedir:%global license %doc}

%files
%license LICENSE
%doc CODE_OF_CONDUCT.md CONTRIBUTING.md README.md
%dir %{katadir}
%dir %{katalibexecdir}
%dir %{katalibexecdir}/rootfs-builder
%dir %{katalibexecdir}/image-builder
%dir %{katalibexecdir}/initrd-builder
%dir %{katalibexecdir}/scripts
%{katalibexecdir}/rootfs-builder/*
%{katalibexecdir}/image-builder/*
%{katalibexecdir}/initrd-builder/*
%{katalibexecdir}/scripts/*

%changelog
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
