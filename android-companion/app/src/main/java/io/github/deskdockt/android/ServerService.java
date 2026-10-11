package io.github.deskdockt.android;

import android.app.*;
import android.content.*;
import android.graphics.Point;
import android.os.*;
import android.view.WindowManager;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.Semaphore;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Versioned, bounded JSON protocol. Only loopback, one authenticated desktop. */
public final class ServerService extends Service {
    public static final int PORT=19673, MAX_FRAME=1048576;
    private static volatile ServerService instance;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final AtomicBoolean running=new AtomicBoolean(false);
    private volatile ServerSocket server,wifiServer;
    private final java.util.concurrent.locks.ReentrantLock session=new java.util.concurrent.locks.ReentrantLock();private volatile Socket client;
    private volatile DataOutputStream output;private volatile boolean authenticated;
    private int failures;private long lockedUntil;
    private final Semaphore pending=new Semaphore(32);
    private final Object writeLock=new Object();
    private final java.util.concurrent.ThreadPoolExecutor replies=new java.util.concurrent.ThreadPoolExecutor(1,1,0,java.util.concurrent.TimeUnit.SECONDS,new java.util.concurrent.ArrayBlockingQueue<>(64));

    public static boolean isRunning(){return instance!=null && instance.running.get();}
    public static boolean isConnected(){return instance!=null && instance.authenticated;}
    public static String pairingCode(Context context) {
        android.content.SharedPreferences preferences=context.getSharedPreferences("pairing",MODE_PRIVATE);
        String code=preferences.getString("code",null);
        if(code==null){code=String.format(java.util.Locale.ROOT,"%08d",new SecureRandom().nextInt(100000000));preferences.edit().putString("code",code).apply();}
        return code;
    }
    @Override public void onCreate() {
        super.onCreate();instance=this;
        NotificationManager manager=getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("sharing","desk dockt sharing",NotificationManager.IMPORTANCE_LOW));
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,ServerService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(this,"sharing").setContentTitle("desk dockt")
            .setContentText("Ready for a paired desktop · tap Stop to disconnect").setSmallIcon(android.R.drawable.ic_menu_share)
            .setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null,"Stop",stop).build()).build();
        startForeground(1,notification);
    }
    @Override public int onStartCommand(Intent intent,int flags,int id) {
        if(intent!=null && "stop".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        if(running.compareAndSet(false,true)){
            new Thread(()->listen(false,PORT),"desk-dockt-adb").start();
            if(intent!=null && intent.getBooleanExtra("wifi",false))new Thread(()->listen(true,intent.getIntExtra("port",19674)),"desk-dockt-wifi").start();
        }
        return START_NOT_STICKY;
    }
    @Override public IBinder onBind(Intent intent){return null;}
    private void listen(boolean wifi,int port) {
        try(ServerSocket listener=wifi?TlsIdentity.server(port):new ServerSocket()) {
            if(wifi)wifiServer=listener;
            else{listener.setReuseAddress(true);listener.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"),port),1);server=listener;}
            while(running.get()) {
                Socket accepted=listener.accept();
                if(!session.tryLock()){accepted.close();continue;}
                try(Socket socket=accepted) {
                    client=socket;socket.setSoTimeout(10000);
                    if(socket instanceof javax.net.ssl.SSLSocket)((javax.net.ssl.SSLSocket)socket).startHandshake();
                    DataInputStream input=new DataInputStream(socket.getInputStream());output=new DataOutputStream(socket.getOutputStream());authenticated=false;
                    if(wifi && SystemClock.elapsedRealtime()<lockedUntil){send(new JSONObject().put("type","error").put("message","Pairing temporarily locked after failed attempts"));continue;}
                    byte[] random=new byte[24];new SecureRandom().nextBytes(random);String nonce=hex(random);
                    Point size=screenSize();send(new JSONObject().put("type","hello").put("protocol","desk-dockt").put("version",2)
                        .put("authentication",wifi?"pairing":"adb").put("width",size.x).put("height",size.y).put("nonce",nonce).put("accessible",ControlService.instance!=null).put("keyboard_selected",String.valueOf(android.provider.Settings.Secure.getString(getContentResolver(),"default_input_method")).startsWith(getPackageName()+"/")));
                    JSONObject auth=read(input);
                    Mac mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(pairingCode(this).getBytes(StandardCharsets.UTF_8),"HmacSHA256"));
                    String expected=hex(mac.doFinal(nonce.getBytes(StandardCharsets.UTF_8)));
                    if(!"authenticate".equals(auth.optString("type")) || (wifi && !MessageDigest.isEqual(expected.getBytes(StandardCharsets.US_ASCII),auth.optString("proof").getBytes(StandardCharsets.US_ASCII)))) {
                        if(++failures>=5){lockedUntil=SystemClock.elapsedRealtime()+60000;failures=0;}
                        send(new JSONObject().put("type","error").put("message","Incorrect pairing code"));continue;
                    }
                    failures=0;authenticated=true;socket.setSoTimeout(0);
                    send(new JSONObject().put("type","ready"));
                    while(running.get()) {
                        JSONObject command=read(input);
                        pending.acquire();
                        main.post(()->{
                            try{ControlService control=ControlService.instance;if(control!=null)control.handle(command);}
                            finally{pending.release();}
                        });
                    }
                } catch(Exception failure) {
                    android.util.Log.d("DeskDockt","Connection ended: "+failure.getClass().getSimpleName());
                    if(failure instanceof javax.net.ssl.SSLHandshakeException)android.util.Log.e("DeskDockt","TLS negotiation failed",failure);
                    // No packet contents, keystrokes, pairing secrets or clipboard are logged.
                } finally {
                    try{accepted.close();}catch(IOException ignored){}
                    authenticated=false;output=null;client=null;
                    main.post(()->{if(ControlService.instance!=null)ControlService.instance.leave();});
                    session.unlock();
                }
            }
        } catch(Exception failure) {android.util.Log.e("DeskDockt","Local transport could not start",failure);if(!wifi)main.post(this::stopSelf);}
    }
    private static JSONObject read(DataInputStream input)throws Exception {
        int length=input.readInt();if(length<=0 || length>MAX_FRAME)throw new IOException("Invalid frame size");
        byte[] data=new byte[length];input.readFully(data);return new JSONObject(new String(data,StandardCharsets.UTF_8));
    }
    private void send(JSONObject message)throws IOException {
        DataOutputStream stream=output;if(stream==null)return;
        byte[] bytes=message.toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>MAX_FRAME)throw new IOException("Frame too large");
        if(Looper.myLooper()==Looper.getMainLooper()){
            try{replies.execute(()->{try{write(stream,bytes);}catch(IOException failure){disconnectClient();}});}
            catch(java.util.concurrent.RejectedExecutionException full){disconnectClient();}
        }else write(stream,bytes);
    }
    private void write(DataOutputStream stream,byte[] bytes)throws IOException {
        synchronized(writeLock){if(stream!=output)return;stream.writeInt(bytes.length);stream.write(bytes);stream.flush();}
    }
    private void disconnectClient(){try{if(client!=null)client.close();}catch(IOException ignored){}}
    private static String hex(byte[] bytes){StringBuilder result=new StringBuilder();for(byte value:bytes)result.append(String.format(java.util.Locale.ROOT,"%02x",value&255));return result.toString();}
    public Point screenSize(){WindowManager wm=getSystemService(WindowManager.class);Point size=new Point();
        if(Build.VERSION.SDK_INT>=30){android.graphics.Rect bounds=wm.getMaximumWindowMetrics().getBounds();size.set(bounds.width(),bounds.height());}
        else wm.getDefaultDisplay().getRealSize(size);return size;}
    public static void clipboard(String text){ServerService service=instance;if(service!=null && service.authenticated)try{service.send(new JSONObject().put("type","clipboard").put("text",text));}catch(Exception ignored){}}
    public static void dimensions(){ServerService service=instance;if(service!=null && service.authenticated)try{Point size=service.screenSize();service.send(new JSONObject().put("type","config").put("width",size.x).put("height",size.y));}catch(Exception ignored){}}
    @Override public void onDestroy(){running.set(false);instance=null;replies.shutdownNow();
        try{if(client!=null)client.close();}catch(IOException ignored){}
        try{if(wifiServer!=null)wifiServer.close();}catch(IOException ignored){}
        try{if(server!=null)server.close();}catch(IOException ignored){}
        if(ControlService.instance!=null)ControlService.instance.leave();
        super.onDestroy();}
}
