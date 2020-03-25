# Release candidate version tracking
%global rcver alpha1
%if 0%{?rcver:1}
%global rcrel .%{rcver}
%global rcstr -%{rcver}
%endif

Version: 1.11.0

%global katalibexecdir          %{_libexecdir}/kata-containers
%global kataosbuilderdir        %{katalibexecdir}/osbuilder
%global katalocalstatecachedir  %{_localstatedir}/cache/kata-containers

%global tag                     %{version}%{?rcstr}
%global git0    https://github.com/kata-containers/osbuilder


Name: kata-osbuilder
Release: 0.1%{?rcrel}%{?dist}
License: ASL 2.0
Summary: Kata guest initrd and image build scripts
URL: %{git0}

# Mirror of kata-agent ExcludeArch
ExcludeArch: %{arm}
ExcludeArch: %{ix86}

Source0: %{git0}/archive/%{version}/osbuilder-%{version}%{?rcstr}.tar.gz
Source2: fedora-kata-osbuilder.sh
Source3: kata-osbuilder-generate.service
%if 0%{?fedora}
Source5: 15-dracut-fedora.conf
%else
Source5: 15-dracut-rhel.conf
%endif

# Force mount_dir to be created in $TMPDIR
# https://github.com/kata-containers/osbuilder/pull/436
Patch01: 0001-image_builder-Force-mount_dir-to-be-created-in-TMPDI.patch


BuildRequires: gcc
BuildRequires: git
BuildRequires: make
BuildRequires: systemd
%{?systemd_requires}
# %check requirements
BuildRequires: kernel
BuildRequires: dracut
BuildRequires: kata-agent >= %{version}
%if 0%{?fedora}
BuildRequires: busybox
%endif

Requires: kata-agent >= %{version}
# dracut/rootfs build deps
Requires: kernel
Requires: dracut
%if 0%{?fedora}
Requires: busybox
%endif
# image build deps
Requires: e2fsprogs
Requires: parted
Requires: qemu-img


%description
%{summary}



%prep
%autosetup -Sgit -n osbuilder-%{version}%{?rcstr}


%build
# Manually build nsdax tool
gcc %{build_cflags} image-builder/nsdax.gpl.c -o nsdax


%install
mkdir -p %{buildroot}%{kataosbuilderdir}
mkdir -p %{buildroot}%{katalocalstatecachedir}
rm rootfs-builder/.gitignore
cp -aR nsdax %{buildroot}/%{kataosbuilderdir}
cp -aR rootfs-builder %{buildroot}/%{kataosbuilderdir}
cp -aR image-builder %{buildroot}/%{kataosbuilderdir}
cp -aR initrd-builder %{buildroot}/%{kataosbuilderdir}
cp -aR scripts %{buildroot}%{kataosbuilderdir}
cp -aR dracut %{buildroot}%{kataosbuilderdir}
cp -a %{SOURCE5} %{buildroot}%{kataosbuilderdir}/dracut/dracut.conf.d/
cp -a %{SOURCE2} %{buildroot}%{kataosbuilderdir}
chmod +x %{buildroot}/%{kataosbuilderdir}/scripts/lib.sh

install -m 0644 -D -t %{buildroot}%{_unitdir} %{_sourcedir}/kata-osbuilder-generate.service


%check
# We could be run in a mock chroot, where uname will report
# different kernel than what we have installed in the chroot.
# So we need to determine a valid kernel version to test against.
KVERSION=$(ls /lib/modules/ | tr "\n" " " | cut -d " " -f 1)
TEST_MODE=1 %{buildroot}%{kataosbuilderdir}/fedora-kata-osbuilder.sh \
    -o %{buildroot}%{kataosbuilderdir} \
    -k "$KVERSION"


%preun
%systemd_preun kata-osbuilder-generate.service
%postun
%systemd_postun kata-osbuilder-generate.service
%post
# Skip running this on Fedora CoreOS / Red Hat CoreOS
if test -w %{katalocalstatecachedir}; then
    %systemd_post kata-osbuilder-generate.service

    TMPOUT="$(mktemp -t kata-rpm-post-XXXXXX.log)"
    echo "Creating kata appliance initrd and filesystem image..."
    bash %{kataosbuilderdir}/fedora-kata-osbuilder.sh > ${TMPOUT} 2>&1
    if test "$?" != "0" ; then
        echo "Building failed. Here is the log details:"
        cat ${TMPOUT}
        exit 1
    fi
fi


%files
%license LICENSE
%doc CODE_OF_CONDUCT.md CONTRIBUTING.md README.md
%dir %{katalibexecdir}
%dir %{kataosbuilderdir}
%dir %{katalocalstatecachedir}

%{kataosbuilderdir}/*
%{_unitdir}/kata-osbuilder-generate.service

# Remove some scripts we don't use
%exclude %{kataosbuilderdir}/rootfs-builder/alpine
%exclude %{kataosbuilderdir}/rootfs-builder/centos
%exclude %{kataosbuilderdir}/rootfs-builder/clearlinux
%exclude %{kataosbuilderdir}/rootfs-builder/debian
%exclude %{kataosbuilderdir}/rootfs-builder/euleros
%exclude %{kataosbuilderdir}/rootfs-builder/fedora
%exclude %{kataosbuilderdir}/rootfs-builder/template
%exclude %{kataosbuilderdir}/rootfs-builder/suse
%exclude %{kataosbuilderdir}/rootfs-builder/ubuntu
%exclude %{kataosbuilderdir}/scripts/install-yq.sh


%changelog
* Wed Mar 25 2020 Cole Robinson <aintdiscole@gmail.com> - 1.11.0-0.1.alpha
- Remove kata-agent, it has moved to its own top level package

* Mon Mar 23 2020 Fabiano Fidêncio <fidencio@redhat.com> - 1.11.0-0.alpha1
- Update to release 1.11.0-alpha1

* Tue Mar 10 2020 Cole Robinson <crobinso@redhat.com> - 1.10.0-8
- Restore needed qemu-img dep

* Fri Mar 06 2020 Cole Robinson <aintdiscole@gmail.com> - 1.10.0-7
- Allow passing non-uname kernel version to osbuilder script

* Thu Mar 05 2020 Cole Robinson <aintdiscole@gmail.com> - 1.10.0-6
- Precompile nsdax binary to drop gcc runtime dep
- Re-add 9p drivers for ease of debugging
- Add %check section
- Add drop in 15-dracut-fedora.conf rather than patch upstream files
- Drop some custom patches
- fedora-kata-osbuilder.sh rework and improvements

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
