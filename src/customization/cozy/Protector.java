package cozy;

import com.google.gson.*;
import java.awt.GraphicsEnvironment;
import java.io.*;
import java.net.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import javax.swing.*;

/** Reconciles verified Packwiz downloads with explicitly recorded file ownership. */
public final class Protector {
    static final Gson JSON = new GsonBuilder().create();
    static final String HOME = ".cozy/";
    final Path root;
    final String staging = HOME + "stage/" + UUID.randomUUID();
    Process runningInstaller;
    final List<String> conflicts = new ArrayList<>();
    final Map<String, Item> items = new LinkedHashMap<>();
    record Item(String id, String path, String algorithm, String hash, boolean optional,
                boolean defaultValue, boolean seed, String name) {}

    Protector(Path root) throws IOException {
        Path requested = root.toAbsolutePath().normalize();
        for (Path part = requested; part != null; part = part.getParent()) {
            if (Files.isSymbolicLink(part) || Files.readAttributes(part,
                    java.nio.file.attribute.BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS).isOther())
                throw new IOException("Unsafe Minecraft directory");
        }
        if (!Files.isDirectory(requested, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Unsafe Minecraft directory");
        // Canonicalize legitimate Windows 8.3 aliases only after rejecting links.
        this.root = requested.toRealPath();
    }

    public static void main(String[] args) throws Exception {
        String pack = null;
        boolean headless = false, options = false;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--pack" -> pack = args[++i];
                case "--headless" -> headless = true;
                case "--options" -> options = true;
                default -> throw new IOException("Unknown argument: " + args[i]);
            }
        }
        if (pack == null) throw new IOException("Missing --pack URL");
        Protector p = new Protector(Path.of("."));
        try {
            p.directory(HOME + "tools");
            try (FileChannel channel = FileChannel.open(p.path(HOME + "lock"),
                    StandardOpenOption.CREATE, StandardOpenOption.WRITE);
                 FileLock lock = channel.tryLock()) {
                if (lock == null) throw new IOException("Another update is running");
                p.recover();
                p.update(URI.create(pack), headless || GraphicsEnvironment.isHeadless(), options);
            }
        } catch (Exception e) {
            try { p.cleanupFailure(); } catch (Exception cleanup) { e.addSuppressed(cleanup); }
            String message = "Update angehalten: " + e.getMessage()
                    + "\nPersönliche Dateien bleiben erhalten. Details: .cozy/conflicts.txt / .cozy/installer.log";
            System.err.println(message);
            if (!headless && !GraphicsEnvironment.isHeadless())
                JOptionPane.showMessageDialog(null, message, "A Cozy Adventure", JOptionPane.ERROR_MESSAGE);
            throw e;
        }
    }

    static void relative(String s) throws IOException {
        if (s == null || s.isEmpty() || s.length() > 512) throw new IOException("Invalid relative path");
        for (String part : s.split("/", -1)) {
            if (part.isEmpty() || part.equals(".") || part.equals("..") || part.endsWith(".") || part.endsWith(" ")
                    || part.chars().anyMatch(c -> c < 32 || c == 127 || "\\<>:\"|?*%".indexOf(c) >= 0)
                    || part.split("\\.")[0].matches("(?i)CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]"))
                throw new IOException("Unsafe path: " + s);
        }
    }

    Path path(String s) throws IOException {
        relative(s);
        Path result = root.resolve(s).normalize();
        if (!result.startsWith(root)) throw new IOException("Path escaped instance");
        for (Path p = result; !p.equals(root); p = p.getParent()) {
            if (Files.exists(p, LinkOption.NOFOLLOW_LINKS)
                    && (Files.isSymbolicLink(p) || !p.toRealPath().equals(p.toAbsolutePath().normalize())))
                throw new IOException("Symlink or junction rejected: " + s);
        }
        if (Files.exists(result) && !Files.isRegularFile(result) && !Files.isDirectory(result))
            throw new IOException("Special file rejected: " + s);
        return result;
    }

    void directory(String s) throws IOException { Files.createDirectories(path(s)); }

    static String digest(byte[] data, String algorithm) throws Exception {
        String a = switch (algorithm) {
            case "sha1" -> "SHA-1";
            case "sha256" -> "SHA-256";
            case "sha512" -> "SHA-512";
            default -> throw new IOException("Unsupported ownership hash: " + algorithm);
        };
        return HexFormat.of().formatHex(MessageDigest.getInstance(a).digest(data));
    }

    static void verify(byte[] data, String algorithm, String expected) throws Exception {
        if (!digest(data, algorithm).equals(expected)) throw new IOException("Hash mismatch (" + algorithm + ")");
    }

    String fingerprint(String s) throws Exception {
        Path p = path(s);
        if (!Files.exists(p)) return null;
        if (!Files.isRegularFile(p)) throw new IOException("Expected regular file: " + s);
        return digest(Files.readAllBytes(p), "sha256");
    }

    boolean matches(String s, String algorithm, String hash) throws Exception {
        Path p = path(s);
        return Files.isRegularFile(p) && digest(Files.readAllBytes(p), algorithm).equals(hash);
    }

    void atomic(String s, byte[] bytes) throws Exception {
        Path dest = path(s);
        Files.createDirectories(dest.getParent());
        Path temp = Files.createTempFile(dest.getParent(), ".cozy-", ".tmp");
        try {
            try (FileChannel c = FileChannel.open(temp, StandardOpenOption.WRITE)) {
                java.nio.ByteBuffer buf = java.nio.ByteBuffer.wrap(bytes);
                while (buf.hasRemaining()) c.write(buf);
                c.force(true);
            }
            path(s);
            Files.move(temp, dest, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(temp); }
    }

    void writeJson(String s, JsonObject object) throws Exception {
        byte[] bytes = (JSON.toJson(object.raw) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if (!Files.isRegularFile(path(s)) || !Arrays.equals(Files.readAllBytes(path(s)), bytes)) atomic(s, bytes);
    }

    JsonObject readJson(String s) throws Exception {
        try (Reader r = Files.newBufferedReader(path(s))) {
            JsonElement value = JsonElement.wrap(JsonParser.parseReader(r));
            if (!value.isJsonObject()) throw new IOException("Expected JSON object: " + s);
            return value.getAsJsonObject();
        } catch (RuntimeException e) { throw new IOException("Invalid metadata: " + s, e); }
    }

    static String str(JsonObject o, String key) throws IOException {
        if (!o.has(key) || !o.get(key).isJsonPrimitive() || !o.get(key).getAsJsonPrimitive().isString())
            throw new IOException("Missing string: " + key);
        return o.get(key).getAsString();
    }

    static boolean bool(JsonObject o, String key, boolean fallback) throws IOException {
        if (!o.has(key)) return fallback;
        if (!o.get(key).isJsonPrimitive() || !o.get(key).getAsJsonPrimitive().isBoolean())
            throw new IOException("Invalid boolean: " + key);
        return o.get(key).getAsBoolean();
    }

    static JsonElement convert(Object v) throws Exception {
        String type = v.getClass().getName();
        if (type.endsWith("$Map")) {
            JsonObject out = new JsonObject();
            Map<?, ?> values = (Map<?, ?>)v.getClass().getMethod("getProperties").invoke(v);
            for (var e : values.entrySet()) out.add((String)e.getKey(), convert(e.getValue()));
            return out;
        }
        if (type.endsWith("$List")) {
            JsonArray out = new JsonArray();
            for (Object e : (List<?>)v.getClass().getMethod("getElements").invoke(v)) out.add(convert(e));
            return out;
        }
        Object value = v.getClass().getMethod("getValue").invoke(v);
        if (value instanceof String s) return new JsonPrimitive(s);
        if (value instanceof Boolean b) return new JsonPrimitive(b);
        if (value instanceof Number n) return new JsonPrimitive(n);
        throw new IOException("Unsupported TOML value");
    }

    static JsonObject toml(byte[] bytes) throws Exception {
        Class<?> value = Class.forName("cc.ekblad.toml.model.TomlValue");
        Object companion = value.getField("Companion").get(null);
        Class<?> parser = Class.forName("cc.ekblad.toml.serialization.TomlDeserializerKt");
        Object parsed = parser.getMethod("from", Class.forName("cc.ekblad.toml.model.TomlValue$Companion"), InputStream.class)
                .invoke(null, companion, new ByteArrayInputStream(bytes));
        return convert(parsed).getAsJsonObject();
    }

    static void permitted(URI uri) throws IOException {
        boolean localTest = "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost());
        if (!("https".equals(uri.getScheme()) || localTest) || uri.getUserInfo() != null || uri.getFragment() != null)
            throw new IOException("Expected HTTPS URL (loopback HTTP allowed for isolated tests)");
    }

    static byte[] fetch(URI uri) throws Exception {
        permitted(uri);
        URLConnection conn = uri.toURL().openConnection();
        if (conn instanceof HttpURLConnection h) h.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(20000); conn.setReadTimeout(30000);
        conn.setRequestProperty("User-Agent", "A-Cozy-Adventure-Customization/1");
        try (InputStream in = conn.getInputStream()) {
            byte[] bytes = in.readNBytes(16 * 1024 * 1024 + 1);
            if (bytes.length > 16 * 1024 * 1024) throw new IOException("Metadata exceeds size limit");
            return bytes;
        }
    }

    void removeTree(String relative) throws Exception {
        Path stage = path(relative);
        if (Files.exists(stage)) {
            List<Path> paths;
            try (var stream = Files.walk(stage)) { paths = stream.sorted(Comparator.reverseOrder()).toList(); }
            for (Path p : paths) path(root.relativize(p).toString().replace('\\', '/'));
            for (Path p : paths) Files.delete(p);
        }
    }

    void clearStage() throws Exception {
        // Unique staging prevents an orphaned native child from touching a later update.
        directory(staging + "/source"); directory(staging + "/files");
    }

    void cleanupFailure() throws Exception {
        // Pending commits and potentially live orphan children retain their own sources.
        if (!Files.exists(path(HOME + "journal.json")) && (runningInstaller == null || !runningInstaller.isAlive()))
            removeTree(staging);
    }

    void snapshot(URI uri, byte[] packBytes) throws Exception {
        JsonObject pack = toml(packBytes), indexLoc = pack.getAsJsonObject("index");
        String indexPath = str(indexLoc, "file"); relative(indexPath);
        byte[] indexBytes = fetch(uri.resolve(indexPath));
        verify(indexBytes, str(indexLoc, "hash-format"), str(indexLoc, "hash"));
        JsonObject index = toml(indexBytes);
        String algorithm = str(index, "hash-format");
        Set<String> destinations = new HashSet<>(), metadata = new HashSet<>();
        for (JsonElement raw : index.getAsJsonArray("files")) {
            JsonObject entry = raw.getAsJsonObject();
            String id = str(entry, "file"); relative(id);
            if (!metadata.add(id.toLowerCase(Locale.ROOT))) throw new IOException("Duplicate index path");
            if (!(id.startsWith("config/") || id.startsWith("mods/") || id.startsWith("resourcepacks/")))
                throw new IOException("Unapproved managed path: " + id);
            byte[] data = fetch(uri.resolve(id));
            verify(data, entry.has("hash-format") ? str(entry, "hash-format") : algorithm, str(entry, "hash"));
            atomic(staging + "/source/" + id, data);
            Item item;
            if (bool(entry, "metafile", false)) {
                JsonObject mod = toml(data);
                String side = mod.has("side") ? str(mod, "side") : "both";
                if (!Set.of("client", "both", "server").contains(side)) throw new IOException("Unknown side");
                String filename = str(mod, "filename"); relative(filename);
                if (filename.contains("/")) throw new IOException("Expected basename");
                String target = id.substring(0, id.lastIndexOf('/') + 1) + filename;
                if (!(target.startsWith("mods/") && target.endsWith(".jar")
                        || target.startsWith("resourcepacks/") && target.endsWith(".zip")))
                    throw new IOException("Unexpected mod/resource extension");
                JsonObject download = mod.getAsJsonObject("download");
                if (download.has("url")) permitted(URI.create(str(download, "url")));
                if (side.equals("server")) continue;
                JsonObject option = mod.has("option") ? mod.getAsJsonObject("option") : new JsonObject();
                item = new Item(id, target, str(download, "hash-format"), str(download, "hash"),
                        bool(option, "optional", false), bool(option, "default", false), false, str(mod, "name"));
            } else {
                if (!id.startsWith("config/")) throw new IOException("Only config files may be seeded directly");
                item = new Item(id, id, entry.has("hash-format") ? str(entry, "hash-format") : algorithm,
                        str(entry, "hash"), false, true, true, id);
            }
            if (!destinations.add(item.path.toLowerCase(Locale.ROOT))) throw new IOException("Colliding official filenames");
            // Validate hash specifications even for disabled components.
            if (!item.hash.matches("[0-9a-f]+") || item.hash.length() != digest(new byte[0], item.algorithm).length())
                throw new IOException("Invalid file hash");
            items.put(id, item);
        }
        atomic(staging + "/source/" + indexPath, indexBytes);
        atomic(staging + "/source/pack.toml", packBytes);
    }

    JsonObject loadState() throws Exception {
        if (Files.exists(path(HOME + "state.json"))) {
            JsonObject state = readJson(HOME + "state.json");
            if (state.get("schema").getAsInt() != 1 || !state.has("entries")) throw new IOException("Unknown protection state");
            for (var e : state.getAsJsonObject("entries").entrySet()) validateRecord(e.getKey(), e.getValue().getAsJsonObject());
            return state;
        }
        if (Files.exists(path(HOME + "initialized")))
            throw new IOException("Protection state is missing; restore .cozy/state.json from backup");
        JsonObject state = new JsonObject(), entries = new JsonObject();
        state.addProperty("schema", 1); state.add("entries", entries);
        JsonArray seeds = new JsonArray(); state.add("seeds", seeds);
        if (!Files.exists(path("packwiz.json"))) return state;
        JsonObject legacy = readJson("packwiz.json");
        if (!legacy.has("cachedFiles") || !legacy.get("cachedFiles").isJsonObject())
            throw new IOException("Invalid legacy Packwiz manifest; preserve it for recovery");
        for (var e : legacy.getAsJsonObject("cachedFiles").entrySet()) {
            String id = e.getKey(); relative(id);
            JsonObject f = e.getValue().getAsJsonObject();
            if (id.startsWith("config/")) seeds.add(new JsonPrimitive(id));
            if (!(id.startsWith("mods/") || id.startsWith("resourcepacks/")) || bool(f, "onlyOtherSide", false)) continue;
            JsonObject r = new JsonObject();
            r.addProperty("enabled", bool(f, "optionValue", true));
            if (f.has("cachedLocation") && !f.get("cachedLocation").isJsonNull()) {
                String target = str(f, "cachedLocation"); relative(target);
                if (!target.startsWith(id.substring(0, id.indexOf('/') + 1))) throw new IOException("Invalid legacy location");
                JsonObject hash = f.getAsJsonObject("linkedFileHash");
                if (hash == null) throw new IOException("Legacy linked hash missing; ownership is uncertain");
                r.addProperty("path", target); r.addProperty("algorithm", str(hash, "type")); r.addProperty("hash", str(hash, "value"));
            }
            validateRecord(id, r); entries.add(id, r);
        }
        return state;
    }

    void validateRecord(String id, JsonObject r) throws Exception {
        relative(id);
        if (!(id.startsWith("mods/") || id.startsWith("resourcepacks/"))) throw new IOException("Invalid ownership identity");
        bool(r, "enabled", true);
        if (r.has("path")) {
            String p = str(r, "path"); relative(p);
            if (!p.startsWith(id.substring(0, id.indexOf('/') + 1))) throw new IOException("Invalid ownership path");
            String alg = str(r, "algorithm"), hash = str(r, "hash");
            if (!hash.matches("[0-9a-f]+") || hash.length() != digest(new byte[0], alg).length()) throw new IOException("Invalid ownership hash");
        }
    }

    boolean enabled(Item item, JsonObject old) throws Exception {
        if (!item.optional) return true;
        if (old == null) return item.defaultValue;
        if (old.has("path")) {
            String p = str(old, "path"), alg = str(old, "algorithm"), hash = str(old, "hash");
            boolean active = matches(p, alg, hash), disabled = matches(p + ".disabled", alg, hash);
            if (active && disabled) throw new IOException("Both enabled and disabled official files exist: " + p);
            if (disabled) return false;
            if (active) return true;
        }
        return bool(old, "enabled", true);
    }

    void choose(Map<String, Boolean> choices, boolean explicit) throws Exception {
        if (!explicit) {
            JOptionPane pane = new JOptionPane("Persönliche Mods und Einstellungen werden geschützt.",
                    JOptionPane.INFORMATION_MESSAGE, JOptionPane.DEFAULT_OPTION, null,
                    new String[]{"Starten", "Auswahl ändern", "Abbrechen"}, "Starten");
            JDialog dialog = pane.createDialog("A Cozy Adventure");
            javax.swing.Timer timer = new javax.swing.Timer(4000, e -> { pane.setValue("Starten"); dialog.dispose(); });
            timer.setRepeats(false); timer.start(); dialog.setVisible(true); timer.stop(); dialog.dispose();
            if ("Starten".equals(pane.getValue())) return;
            if (!"Auswahl ändern".equals(pane.getValue())) throw new IOException("Abgebrochen");
        }
        JPanel list = new JPanel(); list.setLayout(new BoxLayout(list, BoxLayout.Y_AXIS));
        Map<String, JCheckBox> boxes = new LinkedHashMap<>();
        for (Item item : items.values()) if (item.optional) {
            JCheckBox box = new JCheckBox(item.name, choices.get(item.id)); list.add(box); boxes.put(item.id, box);
        }
        JScrollPane scroll = new JScrollPane(list); scroll.setPreferredSize(new java.awt.Dimension(500, 480));
        if (JOptionPane.showConfirmDialog(null, scroll, "Offizielle optionale Bestandteile", JOptionPane.OK_CANCEL_OPTION) != JOptionPane.OK_OPTION)
            throw new IOException("Abgebrochen");
        boxes.forEach((id, box) -> choices.put(id, box.isSelected()));
    }

    void conflict(String message) { conflicts.add(message); }

    void report() throws Exception {
        if (conflicts.isEmpty()) return;
        atomic(HOME + "conflicts.txt", (String.join("\n", conflicts)
                + "\nSichere Auflösung: Betroffene Datei außerhalb von mods/resourcepacks sichern, dann erneut starten."
                + "\nEine bereits entfernte offizielle Komponente wird künftig nicht erneut beansprucht.\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }

    void checkLauncherVersions(byte[] packBytes) throws Exception {
        Path parent = root.getParent();
        if (parent == null) return;
        Path metadata = parent.resolve("mmc-pack.json");
        if (!Files.exists(metadata, LinkOption.NOFOLLOW_LINKS)) return;
        if (!metadata.toRealPath().equals(metadata.toAbsolutePath().normalize()) || !Files.isRegularFile(metadata))
            throw new IOException("Unsafe Prism component metadata");
        JsonObject pack = toml(packBytes);
        JsonObject versions = pack.getAsJsonObject("versions");
        if (versions == null) throw new IOException("Pack versions missing");
        JsonObject launcher;
        try (Reader reader = Files.newBufferedReader(metadata)) {
            launcher = JsonElement.wrap(JsonParser.parseReader(reader)).getAsJsonObject();
        }
        Map<String, String> expected = Map.of("net.minecraft", str(versions, "minecraft"),
                "net.fabricmc.fabric-loader", str(versions, "fabric"));
        Map<String, String> actual = new HashMap<>();
        for (JsonElement raw : launcher.getAsJsonArray("components")) {
            JsonObject c = raw.getAsJsonObject(); String uid = str(c, "uid");
            if (actual.put(uid, str(c, "version")) != null) throw new IOException("Duplicate Prism component");
        }
        for (var e : expected.entrySet()) if (!e.getValue().equals(actual.get(e.getKey())))
            throw new IOException("Prism-Komponente " + e.getKey() + " benötigt " + e.getValue()
                    + ". In Prism unter Instanz bearbeiten → Version entsprechend umstellen, dann erneut starten.");
    }

    void update(URI uri, boolean headless, boolean options) throws Exception {
        byte[] pack = fetch(uri);
        checkLauncherVersions(pack);
        JsonObject state = loadState(), oldEntries = state.getAsJsonObject("entries");
        Map<String, Boolean> selected = null;
        if (state.has("packHash") && str(state, "packHash").equals(digest(pack, "sha256")) && state.has("catalog")) {
            for (JsonElement raw : state.getAsJsonArray("catalog")) {
                JsonObject c = raw.getAsJsonObject();
                Item item = new Item(str(c, "id"), str(c, "path"), str(c, "algorithm"), str(c, "hash"),
                        bool(c, "optional", false), bool(c, "default", true), bool(c, "seed", false), str(c, "name"));
                relative(item.path); relative(item.id);
                if (!(item.path.startsWith("mods/") || item.path.startsWith("resourcepacks/") || item.path.startsWith("config/")))
                    throw new IOException("Invalid cached catalog path");
                items.put(item.id, item);
            }
            Map<String, Boolean> choices = new LinkedHashMap<>();
            boolean unchanged = true;
            for (Item item : items.values()) if (!item.seed) {
                JsonObject old = oldEntries.getAsJsonObject(item.id);
                if (old == null) { unchanged = false; break; }
                boolean on = enabled(item, old); choices.put(item.id, on);
                if (on != bool(old, "enabled", true)) unchanged = false;
                if (old.has("path")) {
                    String actual = str(old, "path") + (on ? "" : ".disabled");
                    if (!matches(actual, str(old, "algorithm"), str(old, "hash"))) unchanged = false;
                    String other = str(old, "path") + (on ? ".disabled" : "");
                    if (Files.exists(path(other))) unchanged = false;
                } else if (Files.exists(path(item.path)) || Files.exists(path(item.path + ".disabled"))) unchanged = false;
            }
            if (unchanged) {
                Map<String, Boolean> original = new LinkedHashMap<>(choices);
                if (!headless) choose(choices, options);
                if (original.equals(choices)) {
                    System.out.println("Customization protection: already up to date (0 file changes)."); return;
                }
                selected = choices;
            }
            items.clear();
        }
        clearStage(); snapshot(uri, pack);
        Set<String> seeded = new LinkedHashSet<>();
        if (state.has("seeds")) for (JsonElement seed : state.getAsJsonArray("seeds")) {
            String name = seed.getAsString(); relative(name);
            if (!name.startsWith("config/")) throw new IOException("Invalid seeded config path");
            seeded.add(name);
        }
        Map<String, Boolean> choices = new LinkedHashMap<>();
        for (Item item : items.values()) if (!item.seed)
            choices.put(item.id, enabled(item, oldEntries.has(item.id) ? oldEntries.getAsJsonObject(item.id) : null));
        if (selected != null) choices.putAll(selected);
        else if (!headless) choose(choices, options);
        // A fresh, bounded manifest prevents upstream removal logic from seeing player files.
        JsonObject nativeManifest = new JsonObject(), cached = new JsonObject();
        nativeManifest.add("cachedFiles", cached); nativeManifest.addProperty("cachedSide", "client");
        for (Item item : items.values()) {
            JsonObject f = new JsonObject();
            f.addProperty("isOptional", item.optional); f.addProperty("optionValue", item.seed || choices.get(item.id));
            cached.add(item.id, f);
            if (Files.isRegularFile(path(item.path)) && matches(item.path, item.algorithm, item.hash))
                atomic(staging + "/files/" + item.path, Files.readAllBytes(path(item.path)));
        }
        writeJson(staging + "/files/packwiz.json", nativeManifest);
        Path javaExecutable = Path.of(System.getProperty("java.home"), "bin", System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java");
        List<String> command = List.of(javaExecutable.toString(), "-cp", path(HOME + "tools/packwiz-installer.jar").toString(),
                "link.infra.packwiz.installer.Main", "-g", "-s", "client", "--multimc-folder", ".",
                path(staging + "/source/pack.toml").toUri().toString());
        Process process = new ProcessBuilder(command).directory(path(staging + "/files").toFile())
                .redirectErrorStream(true).redirectOutput(path(staging + "/installer.log").toFile()).start();
        runningInstaller = process;
        if (!process.waitFor(5, java.util.concurrent.TimeUnit.MINUTES)) { process.destroyForcibly(); throw new IOException("Installer timed out"); }
        atomic(HOME + "installer.log", Files.readAllBytes(path(staging + "/installer.log")));
        if (process.exitValue() != 0) throw new IOException("Official Packwiz installer failed; see .cozy/installer.log");
        for (Item item : items.values()) if (item.seed || choices.get(item.id)) {
            if (!matches(staging + "/files/" + item.path, item.algorithm, item.hash))
                throw new IOException("Incomplete or invalid staged download: " + item.path);
        }
        JsonArray operations = new JsonArray();
        Map<String, JsonObject> byPath = new LinkedHashMap<>();
        JsonObject nextEntries = new JsonObject();
        boolean blocked = false;
        // Retire ownership immediately after a removal, including disabled/null-location entries.
        for (var e : oldEntries.entrySet()) {
            JsonObject old = e.getValue().getAsJsonObject();
            if (!old.has("path")) continue;
            String p = str(old, "path"), alg = str(old, "algorithm"), hash = str(old, "hash");
            for (String candidate : List.of(p, p + ".disabled")) {
                if (!Files.exists(path(candidate))) continue;
                if (matches(candidate, alg, hash)) {
                    addOperation(byPath, candidate, fingerprint(candidate), null, null);
                } else {
                    conflict("Veränderte persönliche/unklare Datei erhalten: " + candidate);
                    if (items.containsKey(e.getKey())) blocked = true;
                }
            }
        }
        for (Item item : items.values()) {
            if (item.seed) {
                if (!seeded.contains(item.id) && !Files.exists(path(item.path))) addOperation(byPath, item.path, null,
                        fingerprint(staging + "/files/" + item.path), staging + "/files/" + item.path);
                seeded.add(item.id);
                continue;
            }
            boolean on = choices.get(item.id);
            JsonObject r = new JsonObject(); r.addProperty("enabled", on);
            if (on) {
                r.addProperty("path", item.path); r.addProperty("algorithm", item.algorithm); r.addProperty("hash", item.hash);
            }
            nextEntries.add(item.id, r);
            String target = on ? item.path : item.path + ".disabled";
            String existing = fingerprint(target);
            for (String candidate : List.of(item.path, item.path + ".disabled")) {
                if (fingerprint(candidate) != null && !byPath.containsKey(candidate)) {
                    // An exact hash is insufficient to claim an unrecorded personal file.
                    conflict("Dateinamenskollision; persönliche Datei erhalten: " + candidate); blocked = true;
                }
            }
            if (on) addOperation(byPath, target, existing, fingerprint(staging + "/files/" + item.path), staging + "/files/" + item.path);
            else {
                // Disabled updates keep the previous owned bytes until re-enabled; no download is required.
                JsonObject old = oldEntries.has(item.id) ? oldEntries.getAsJsonObject(item.id) : null;
                if (old != null && old.has("path")) {
                    String previous = str(old, "path");
                    String source = matches(previous + ".disabled", str(old, "algorithm"), str(old, "hash")) ? previous + ".disabled" : previous;
                    if (matches(source, str(old, "algorithm"), str(old, "hash"))) {
                        // Keep the old filename/hash so later removal can prove ownership.
                        nextEntries.add(item.id, old.deepCopy()); nextEntries.getAsJsonObject(item.id).addProperty("enabled", false);
                        String disabled = previous + ".disabled";
                        String staged = staging + "/disabled/" + previous;
                        atomic(staged, Files.readAllBytes(path(source)));
                        addOperation(byPath, disabled, fingerprint(disabled), fingerprint(staged), staged);
                    }
                }
            }
        }
        report();
        if (blocked) throw new IOException("Ownership conflict; see .cozy/conflicts.txt");
        for (JsonObject op : byPath.values()) if (!Objects.equals(nullable(op, "before"), nullable(op, "after"))) operations.add(op);
        JsonObject next = new JsonObject(); next.addProperty("schema", 1); next.add("entries", nextEntries);
        JsonArray nextSeeds = new JsonArray(); for (String seed : seeded) nextSeeds.add(new JsonPrimitive(seed));
        next.add("seeds", nextSeeds);
        JsonArray catalog = new JsonArray();
        for (Item item : items.values()) {
            JsonObject c = new JsonObject();
            c.addProperty("id", item.id); c.addProperty("path", item.path); c.addProperty("algorithm", item.algorithm);
            c.addProperty("hash", item.hash); c.addProperty("optional", item.optional); c.addProperty("default", item.defaultValue);
            c.addProperty("seed", item.seed); c.addProperty("name", item.name); catalog.add(c);
        }
        next.add("catalog", catalog);
        next.addProperty("packHash", digest(pack, "sha256"));
        JsonObject journal = new JsonObject(); journal.addProperty("schema", 1); journal.add("operations", operations); journal.add("state", next);
        journal.addProperty("staging", staging);
        writeJson(HOME + "journal.json", journal); recover();
        System.out.println("Customization protection: update complete (" + operations.size() + " file changes).");
    }

    static String nullable(JsonObject o, String key) {
        JsonElement value = o.get(key); return value == null || value.isJsonNull() ? null : value.getAsString();
    }

    void addOperation(Map<String, JsonObject> ops, String p, String before, String after, String source) {
        JsonObject op = new JsonObject(); op.addProperty("path", p); op.addProperty("before", before);
        op.addProperty("after", after); op.addProperty("source", source); ops.put(p, op);
    }

    void recover() throws Exception {
        if (!Files.exists(path(HOME + "journal.json"))) return;
        JsonObject journal = readJson(HOME + "journal.json");
        if (journal.get("schema").getAsInt() != 1) throw new IOException("Unknown transaction schema");
        JsonObject next = journal.getAsJsonObject("state");
        for (var e : next.getAsJsonObject("entries").entrySet()) validateRecord(e.getKey(), e.getValue().getAsJsonObject());
        // Preflight the entire journal before changing any file, including on interrupted restarts.
        for (JsonElement raw : journal.getAsJsonArray("operations")) {
            JsonObject op = raw.getAsJsonObject(); String p = str(op, "path"); relative(p);
            if (!(p.startsWith("mods/") || p.startsWith("resourcepacks/") || p.startsWith("config/"))) throw new IOException("Invalid journal destination");
            String now = fingerprint(p), before = nullable(op, "before"), after = nullable(op, "after");
            if (!Objects.equals(now, before) && !Objects.equals(now, after)) throw new IOException("File changed during transaction: " + p);
            if (after != null) {
                String source = str(op, "source");
                if (!source.startsWith(HOME + "stage/")) throw new IOException("Invalid transaction source");
                if (!after.equals(fingerprint(source))) throw new IOException("Damaged transaction source");
            }
        }
        for (JsonElement raw : journal.getAsJsonArray("operations")) {
            JsonObject op = raw.getAsJsonObject(); String p = str(op, "path"), after = nullable(op, "after");
            String now = fingerprint(p);
            if (Objects.equals(now, after)) continue;
            if (!Objects.equals(now, nullable(op, "before"))) throw new IOException("Concurrent change: " + p);
            if (after == null) Files.delete(path(p));
            else atomic(p, Files.readAllBytes(path(str(op, "source"))));
        }
        writeJson(HOME + "state.json", next);
        if (!Files.exists(path(HOME + "initialized"))) atomic(HOME + "initialized", new byte[]{1});
        // Retain the legacy evidence, but never leave a second active ownership ledger.
        if (Files.exists(path("packwiz.json"))) {
            if (!Files.exists(path(HOME + "legacy-packwiz.json")))
                atomic(HOME + "legacy-packwiz.json", Files.readAllBytes(path("packwiz.json")));
            JsonObject retired = new JsonObject(); retired.add("cachedFiles", new JsonObject());
            retired.addProperty("customizationProtection", "Ownership moved to .cozy/state.json; do not run the native launcher directly.");
            writeJson("packwiz.json", retired);
        }
        Files.delete(path(HOME + "journal.json"));
        if (journal.has("staging")) {
            String completed = str(journal, "staging");
            relative(completed);
            if (!completed.startsWith(HOME + "stage/") || completed.substring((HOME + "stage/").length()).contains("/"))
                throw new IOException("Invalid completed staging path");
            removeTree(completed);
        }
    }
}
