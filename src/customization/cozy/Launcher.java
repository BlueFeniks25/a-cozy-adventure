package cozy;

import java.awt.GraphicsEnvironment;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import javax.swing.JFileChooser;
import javax.swing.JOptionPane;

/** JDK-only entry point and explicit migration for existing Prism instances. */
public final class Launcher {
    private static final String INSTALLER_SHA256 = "c9f646908d340d84773948a9a7d98bc1dae250d35e1016dc6e2b8459760b5598";
    // GitHub v1.0.0 release asset 656125771 digest, checked 2026-10-19.
    private static final String PREVIOUS_LAUNCHER_SHA256 = "99dc680b056805515d48cab3800a096239b4206ee584402873107fe06023ffc6";
    private static final String PACK = "https://bluefeniks25.github.io/a-cozy-adventure/pack.toml";
    private static final String OLD_COMMAND = "\\\"$INST_JAVA\\\" -jar packwiz-installer-bootstrap.jar " + PACK;
    private static final String COMMAND = "\\\"$INST_JAVA\\\" -jar cozy-customization.jar --pack " + PACK;

    private Launcher() { }

    public static void main(String[] args) {
        try {
            if (args.length == 0) {
                chooseInstance();
            } else if (args.length == 2 && args[0].equals("--migrate")) {
                migrate(Path.of(args[1]));
                System.out.println("Migration complete. Start this instance in Prism Launcher.");
            } else if (args.length >= 2 && args[0].equals("--pack")) {
                runProtector(args);
            } else {
                throw new IllegalArgumentException("Use --pack URL [--headless] [--options] or --migrate INSTANCE_DIRECTORY.");
            }
        } catch (Throwable error) {
            if (error instanceof InvocationTargetException && error.getCause() != null) {
                error = error.getCause();
            }
            String message = "A Cozy Adventure: " + error.getMessage();
            System.err.println(message);
            if (!GraphicsEnvironment.isHeadless() && !Arrays.asList(args).contains("--headless")) {
                JOptionPane.showMessageDialog(null, message, "A Cozy Adventure", JOptionPane.ERROR_MESSAGE);
            }
            System.exit(1);
        }
    }

    private static void chooseInstance() throws Exception {
        if (GraphicsEnvironment.isHeadless()) {
            throw new IllegalArgumentException("Select an instance with --migrate INSTANCE_DIRECTORY.");
        }
        JFileChooser chooser = new JFileChooser();
        chooser.setDialogTitle("A Cozy Adventure: Prism-Instanzordner auswählen");
        chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
        if (chooser.showOpenDialog(null) != JFileChooser.APPROVE_OPTION) {
            return;
        }
        migrate(chooser.getSelectedFile().toPath());
        JOptionPane.showMessageDialog(null,
                "Migration abgeschlossen. Die Instanz kann jetzt in Prism Launcher gestartet werden.",
                "A Cozy Adventure", JOptionPane.INFORMATION_MESSAGE);
    }

    private static Path self() throws Exception {
        Path result = Path.of(Launcher.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        regular(result);
        return result;
    }

    /** Reject symbolic links in the entire destination ancestry before any writes. */
    private static void safe(Path path) throws Exception {
        for (Path part = path.toAbsolutePath(); part != null; part = part.getParent()) {
            if (Files.isSymbolicLink(part)) {
                throw new IllegalArgumentException("Symbolic links are not allowed: " + path.getFileName());
            }
            // Windows junctions and other reparse points must also be rejected.
            if (Files.exists(part, LinkOption.NOFOLLOW_LINKS)
                    && Files.readAttributes(part, java.nio.file.attribute.BasicFileAttributes.class,
                            LinkOption.NOFOLLOW_LINKS).isOther()) {
                throw new IllegalArgumentException("Special file paths are not allowed: " + path.getFileName());
            }
        }
    }

    private static void regular(Path path) throws Exception {
        safe(path);
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("Expected a regular file: " + path.getFileName());
        }
    }

    private static void atomicWrite(Path path, byte[] data) throws Exception {
        safe(path);
        Path temporary = Files.createTempFile(path.getParent(), ".cozy-", ".tmp");
        try {
            Files.write(temporary, data);
            safe(path);
            Files.move(temporary, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private static void createBackup(Path path, byte[] data) throws Exception {
        safe(path);
        Path temporary = Files.createTempFile(path.getParent(), ".cozy-backup-", ".tmp");
        try {
            Files.write(temporary, data);
            safe(path);
            // Same-directory rename exposes only a complete backup; never replace an existing one.
            Files.move(temporary, path);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    static void migrate(Path selected) throws Exception {
        Path instance = selected.toAbsolutePath().normalize();
        safe(instance);
        Path config = instance.resolve("instance.cfg");
        regular(config);
        regular(instance.resolve("mmc-pack.json"));
        Path visible = instance.resolve("minecraft");
        Path hidden = instance.resolve(".minecraft");
        safe(visible);
        safe(hidden);
        if (Files.exists(visible) == Files.exists(hidden)) {
            throw new IllegalArgumentException("Expected exactly one minecraft or .minecraft directory in the Prism instance.");
        }
        Path minecraft = Files.exists(visible) ? visible : hidden;
        if (!Files.isDirectory(minecraft, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("Minecraft path must be a directory.");
        }
        byte[] original = Files.readAllBytes(config);
        String text = new String(original, StandardCharsets.UTF_8);
        String newline = text.contains("\r\n") ? "\r\n" : "\n";
        List<String> lines = new ArrayList<>(Arrays.asList(text.split("\\r?\\n", -1)));
        boolean general = false;
        int command = -1;
        int override = -1;
        int generalCount = 0;
        for (int i = 0; i < lines.size(); i++) {
            String line = lines.get(i).strip();
            if (line.startsWith("[") && line.endsWith("]")) {
                general = line.equals("[General]");
                if (general) generalCount++;
            }
            if (general && line.startsWith("PreLaunchCommand=")) {
                if (command >= 0) throw new IllegalArgumentException("Duplicate PreLaunchCommand in instance.cfg.");
                command = i;
            }
            if (general && line.startsWith("OverrideCommands=")) {
                if (override >= 0) throw new IllegalArgumentException("Duplicate OverrideCommands in instance.cfg.");
                override = i;
            }
        }
        if (generalCount != 1 || command < 0 || override < 0) {
            throw new IllegalArgumentException("Unrecognized Prism instance.cfg; no settings were changed.");
        }
        String previous = lines.get(command).strip().substring("PreLaunchCommand=".length());
        if (!previous.equals(OLD_COMMAND) && !previous.equals(COMMAND)) {
            throw new IllegalArgumentException("Unknown PreLaunchCommand; preserve it and resolve the conflict before migration.");
        }
        Path target = minecraft.resolve("cozy-customization.jar");
        Path executable = self();
        byte[] jar = Files.readAllBytes(executable);
        safe(target);
        byte[] previousJar = null;
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            regular(target);
            byte[] existing = Files.readAllBytes(target);
            if (!Arrays.equals(existing, jar)) {
                String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(existing));
                if (!previous.equals(COMMAND) || !digest.equals(PREVIOUS_LAUNCHER_SHA256))
                    throw new IllegalArgumentException("An existing cozy-customization.jar differs; preserve it and resolve the collision first.");
                previousJar = existing;
            }
        }
        Path backup = instance.resolve("instance.cfg.before-customization");
        safe(backup);
        if (Files.exists(backup, LinkOption.NOFOLLOW_LINKS)) {
            regular(backup);
            if (!previous.equals(COMMAND) && !Arrays.equals(Files.readAllBytes(backup), original)) {
                throw new IllegalArgumentException("Migration backup already exists with different settings.");
            }
        }
        lines.set(command, "PreLaunchCommand=" + COMMAND);
        lines.set(override, "OverrideCommands=true");
        byte[] updated = String.join(newline, lines).getBytes(StandardCharsets.UTF_8);
        if (previousJar != null) {
            Path jarBackup = minecraft.resolve("cozy-customization.jar.before-v1.0.1");
            safe(jarBackup);
            if (Files.exists(jarBackup, LinkOption.NOFOLLOW_LINKS)) {
                regular(jarBackup);
                if (!Arrays.equals(Files.readAllBytes(jarBackup), previousJar))
                    throw new IllegalArgumentException("Protection upgrade backup differs; no files were replaced.");
            } else createBackup(jarBackup, previousJar);
            regular(target);
            if (!Arrays.equals(Files.readAllBytes(target), previousJar)
                    || !Arrays.equals(original, Files.readAllBytes(config)))
                throw new IllegalArgumentException("Protection or settings changed during upgrade; no replacement performed.");
            atomicWrite(target, jar);
            // Preserve the entire .cozy ownership state and existing Prism command.
            return;
        }
        if (Arrays.equals(original, updated) && Files.exists(target)) return;
        if (!Files.exists(backup)) createBackup(backup, original);
        if (!Files.exists(target)) atomicWrite(target, jar);
        // A concurrent settings edit must never be overwritten by migration.
        if (!Arrays.equals(original, Files.readAllBytes(config))) {
            throw new IllegalArgumentException("instance.cfg changed during migration; original settings were preserved.");
        }
        atomicWrite(config, updated);
    }

    private static void runProtector(String[] args) throws Exception {
        Path root = Path.of("").toAbsolutePath().normalize();
        safe(root);
        Path tools = root.resolve(".cozy/tools");
        safe(tools);
        byte[] nativeJar;
        try (InputStream stream = Launcher.class.getResourceAsStream("/cozy/packwiz-installer.jar")) {
            if (stream == null) throw new IllegalArgumentException("Missing embedded official Packwiz installer.");
            nativeJar = stream.readAllBytes();
        }
        if (!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(nativeJar)).equals(INSTALLER_SHA256)) {
            throw new IllegalArgumentException("Embedded Packwiz installer integrity check failed.");
        }
        Files.createDirectories(tools);
        Path nativeFile = tools.resolve("packwiz-installer.jar");
        safe(nativeFile);
        if (Files.exists(nativeFile, LinkOption.NOFOLLOW_LINKS)) regular(nativeFile);
        if (!Files.exists(nativeFile) || !Arrays.equals(Files.readAllBytes(nativeFile), nativeJar)) {
            atomicWrite(nativeFile, nativeJar);
        }
        try (URLClassLoader loader = new URLClassLoader(new java.net.URL[] {
                self().toUri().toURL(), nativeFile.toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            Thread.currentThread().setContextClassLoader(loader);
            loader.loadClass("cozy.Protector").getMethod("main", String[].class).invoke(null, (Object) args);
        }
    }
}
