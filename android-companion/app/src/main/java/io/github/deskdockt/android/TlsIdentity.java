package io.github.deskdockt.android;

import android.security.keystore.*;
import java.security.*;
import java.security.spec.ECGenParameterSpec;
import java.math.BigInteger;
import java.util.Date;
import javax.net.ssl.*;
import javax.security.auth.x500.X500Principal;

/** Device-local TLS key; users verify the displayed certificate fingerprint. */
final class TlsIdentity {
    private static final String ALIAS="desk-dockt-tls-v2";
    private static synchronized KeyStore store() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias(ALIAS)){
            KeyPairGenerator generator=KeyPairGenerator.getInstance("EC","AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_SIGN|KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_NONE,KeyProperties.DIGEST_SHA256,KeyProperties.DIGEST_SHA384)
                .setCertificateSubject(new X500Principal("CN=desk dockt"))
                .setCertificateSerialNumber(new BigInteger(128,new SecureRandom()))
                .setCertificateNotBefore(new Date(0)).setCertificateNotAfter(new Date(4102444800000L)).build());
            generator.generateKeyPair();
        }
        return store;
    }
    static String fingerprint() throws Exception {
        byte[] digest=MessageDigest.getInstance("SHA-256").digest(store().getCertificate(ALIAS).getEncoded());
        StringBuilder text=new StringBuilder();for(byte value:digest)text.append(String.format(java.util.Locale.ROOT,"%02x",value&255));return text.toString();
    }
    private static SSLContext context() throws Exception {
        KeyManagerFactory managers=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());managers.init(store(),null);
        SSLContext context=SSLContext.getInstance("TLS");context.init(managers.getKeyManagers(),null,new SecureRandom());return context;
    }
    static SSLServerSocket server(int port) throws Exception {
        SSLServerSocket socket=(SSLServerSocket)context().getServerSocketFactory().createServerSocket();
        socket.setReuseAddress(true);socket.setUseClientMode(false);socket.setEnabledProtocols(new String[]{"TLSv1.2"});
        socket.bind(new java.net.InetSocketAddress("0.0.0.0",port),2);return socket;
    }
}
