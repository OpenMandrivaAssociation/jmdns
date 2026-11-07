Name:		jmdns
Version:	3.6.5
Release:	1
Summary:	Java implementation of multicast DNS
Group:		Development/Java
License:	ASL 2.0
URL:		https://github.com/jmdns/jmdns
Source0:	https://github.com/jmdns/jmdns/archive/refs/tags/v%{version}.tar.gz#/jmdns-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	python
# Literal, so the first rpmbuild -bs records them before sysjar is installed.
BuildRequires:	maven
BuildRequires:	java-current-devel
BuildRequires:	mvn(org.slf4j:slf4j-api)
# The published slf4j-api POM parents this, and the slf4j package does not require it.
BuildRequires:	mvn(org.slf4j:slf4j-parent:pom::)
BuildSystem:	maven
BuildOption(install):	--file-name jmdns --alias javax.jmdns:jmdns --alias org.jenkins-ci:jmdns

Obsoletes:	%{name}-javadoc < %{version}-%{release}

%description
JmDNS is a Java implementation of multicast DNS for service registration
and discovery on a local network. 3.6.5 requires Java 8. It receives mDNS
on a wildcard socket outside Windows, ignores packets from a different
address family, restores unicast responses to legacy queriers, and does
not set the TC bit when a multicast response rolls over. The library is
built against the system SLF4J 1.7 API. The old javax.jmdns and
org.jenkins-ci coordinates still resolve to this jar. Tests are skipped.
The automatic module name is javax.jmdns.

%prep
%autosetup -n jmdns-%{version}
python - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", NS)
tree = ET.parse("pom.xml")
root = tree.getroot()
parent_of = {child: parent for parent in root.iter() for child in list(parent)}

def q(name):
    return "{" + NS + "}" + name

removed_deps = 0
slf4j = 0
for dep in list(root.iter(q("dependency"))):
    scope = dep.find(q("scope"))
    if scope is not None and (scope.text or "") == "test":
        parent_of[dep].remove(dep)
        removed_deps += 1
        continue
    art = dep.find(q("artifactId"))
    if art is not None and art.text == "slf4j-api":
        ver = dep.find(q("version"))
        if ver is None:
            raise SystemExit("slf4j-api has no version")
        ver.text = "1.7.36"
        slf4j += 1

removed_plugins = 0
removed_st = 0
removed_manifest = 0
removed_exec = 0
for plugin in list(root.iter(q("plugin"))):
    art = plugin.find(q("artifactId"))
    if art is None:
        continue
    if art.text == "maven-bundle-plugin":
        parent_of[plugin].remove(plugin)
        removed_plugins += 1
        continue
    if art.text == "maven-compiler-plugin":
        config = plugin.find(q("configuration"))
        if config is None:
            raise SystemExit("compiler plugin has no configuration")
        for child_name in ("source", "target"):
            for child in list(config.findall(q(child_name))):
                config.remove(child)
                removed_st += 1
    if art.text == "maven-jar-plugin":
        for node in list(plugin.iter(q("manifestFile"))):
            owner = parent_of.get(node)
            if owner is None:
                raise SystemExit("manifestFile parent missing")
            owner.remove(node)
            removed_manifest += 1
        # An id-less jar execution is "default" and runs in addition to
        # the lifecycle default-jar, so the second jar goal fails.
        for executions in list(plugin.findall(q("executions"))):
            plugin.remove(executions)
            removed_exec += 1

if removed_deps != 4 or slf4j != 1 or removed_plugins != 1 or removed_st != 2 or removed_manifest != 1 or removed_exec != 1:
    raise SystemExit(
        "edits deps " + str(removed_deps)
        + " slf4j " + str(slf4j)
        + " plugins " + str(removed_plugins)
        + " st " + str(removed_st)
        + " manifest " + str(removed_manifest)
        + " exec " + str(removed_exec)
    )
tree.write("pom.xml", encoding="utf-8", xml_declaration=True)
text = Path("pom.xml").read_text(encoding="utf-8")
for needle in (
    "<artifactId>slf4j-api</artifactId>",
    "<version>1.7.36</version>",
    "<release>${jvm.version}</release>",
    "Automatic-Module-Name",
    "javax.jmdns",
):
    if needle not in text:
        raise SystemExit("pom missing " + needle)
for needle in (
    "<artifactId>junit-jupiter-api</artifactId>",
    "<artifactId>junit-jupiter-engine</artifactId>",
    "<artifactId>mockito-inline</artifactId>",
    "<artifactId>logback-classic</artifactId>",
    "<scope>test</scope>",
    "manifestFile",
):
    if needle in text:
        raise SystemExit("pom still contains " + needle)
compiler = text.split("<artifactId>maven-compiler-plugin</artifactId>", 1)[1].split("</plugin>", 1)[0]
if "<source>" in compiler or "<target>" in compiler or "<release>${jvm.version}</release>" not in compiler:
    raise SystemExit("compiler configuration was not reduced to release")
jar = text.split("<artifactId>maven-jar-plugin</artifactId>", 1)[1].split("</plugin>", 1)[0]
if "<executions>" in jar or "<goal>jar</goal>" in jar or "manifestFile" in jar:
    raise SystemExit("jar plugin still attaches a second jar")
if "Automatic-Module-Name" not in jar or "javax.jmdns" not in jar:
    raise SystemExit("jar plugin lost the module name")
files = list(Path("src/main/java").rglob("*.java"))
if len(files) != 59:
    raise SystemExit("unexpected java file count " + str(len(files)))
PY

%build -a
cat > manifest-addition <<'EOF'
Automatic-Module-Name: javax.jmdns
EOF
jar ufm target/jmdns-%{version}.jar manifest-addition
java --module-path target/jmdns-%{version}.jar --describe-module javax.jmdns > module-describe.txt
# A versioned jar prints "name@version ... automatic", not "name automatic".
grep -q '^javax.jmdns' module-describe.txt || { cat module-describe.txt; exit 1; }
grep -q ' automatic$' module-describe.txt || { cat module-describe.txt; exit 1; }

%files -f .mfiles
%doc LICENSE NOTICE.txt README.md
