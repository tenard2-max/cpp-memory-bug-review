# Heavier Direct3D9 present loop to keep WDDM from parking GPU during CUDA.
$ErrorActionPreference = "Stop"
Add-Type -Language CSharp -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

public class GpuTurboD3D : Form
{
    [DllImport("d3d9.dll")] static extern IntPtr Direct3DCreate9(uint SDKVersion);
    [StructLayout(LayoutKind.Sequential)] struct D3DPRESENT_PARAMETERS {
        public uint BackBufferWidth, BackBufferHeight, BackBufferFormat, BackBufferCount;
        public int MultiSampleType; public uint MultiSampleQuality;
        public uint SwapEffect; public IntPtr hDeviceWindow; public bool Windowed;
        public bool EnableAutoDepthStencil; public uint AutoDepthStencilFormat;
        public uint Flags; public uint FullScreen_RefreshRateInHz, PresentationInterval;
    }
    [ComImport, Guid("81BDCBCA-64D4-426d-AE8D-AD0147F4275C"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IDirect3D9 {
        void RegisterSoftwareDevice(IntPtr a);
        uint GetAdapterCount();
        void _a(); void _b(); void _c(); void _d(); void _e(); void _f(); void _g(); void _h(); void _i(); void _j(); void _k(); void _l(); void _m();
        [PreserveSig] int CreateDevice(uint adapter, uint type, IntPtr hwnd, uint behavior, ref D3DPRESENT_PARAMETERS pp, out IntPtr device);
    }
    [ComImport, Guid("D0223B96-BF7A-43fd-92BD-A43B0D82B9EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IDirect3DDevice9 {
        void _a(); void _b(); void _c(); void _d(); void _e(); void _f(); void _g(); void _h(); void _i(); void _j(); void _k(); void _l(); void _m(); void _n(); void _o(); void _p();
        [PreserveSig] int Clear(uint c, IntPtr r, uint flags, uint color, float z, uint stencil);
        void _q();
        [PreserveSig] int BeginScene();
        [PreserveSig] int EndScene();
        [PreserveSig] int Present(IntPtr s, IntPtr d, IntPtr w, IntPtr dirty);
    }

    IntPtr _d3d, _devPtr;
    IDirect3D9 _d3dObj;
    IDirect3DDevice9 _dev;
    System.Windows.Forms.Timer _timer;
    int _frame;
    Label _label;

    public GpuTurboD3D()
    {
        Text = "GPU Turbo D3D - leave open during LLM";
        Width = 480; Height = 200;
        TopMost = true;
        FormBorderStyle = FormBorderStyle.FixedToolWindow;
        BackColor = System.Drawing.Color.Black;
        _label = new Label {
            Dock = DockStyle.Fill,
            ForeColor = System.Drawing.Color.Lime,
            Font = new System.Drawing.Font("Consolas", 14),
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
            Text = "starting D3D..."
        };
        Controls.Add(_label);
        Load += OnLoad;
        FormClosing += (_, e) => {
            if (MessageBox.Show(this, "Close GPU Turbo?", "GPU Turbo", MessageBoxButtons.YesNo) != DialogResult.Yes)
                e.Cancel = true;
        };
    }

    void OnLoad(object sender, EventArgs e)
    {
        const uint D3D_SDK_VERSION = 32;
        _d3d = Direct3DCreate9(D3D_SDK_VERSION);
        if (_d3d == IntPtr.Zero) throw new Exception("Direct3DCreate9 failed");
        _d3dObj = (IDirect3D9)Marshal.GetObjectForIUnknown(_d3d);
        var pp = new D3DPRESENT_PARAMETERS {
            Windowed = true,
            SwapEffect = 1, // DISCARD
            BackBufferFormat = 22, // X8R8G8B8
            PresentationInterval = 0x80000000u, // IMMEDIATE
            hDeviceWindow = Handle,
            BackBufferWidth = (uint)ClientSize.Width,
            BackBufferHeight = (uint)ClientSize.Height,
            EnableAutoDepthStencil = false
        };
        // HAL + FPU_PRESERVE + MULTITHREADED + HARDWARE_VERTEXPROCESSING
        int hr = _d3dObj.CreateDevice(0, 1, Handle, 0x00000040 | 0x00000004 | 0x00000010, ref pp, out _devPtr);
        if (hr < 0 || _devPtr == IntPtr.Zero) throw new Exception("CreateDevice failed HR=0x" + hr.ToString("X"));
        _dev = (IDirect3DDevice9)Marshal.GetObjectForIUnknown(_devPtr);
        _timer = new System.Windows.Forms.Timer { Interval = 1 };
        _timer.Tick += (_, __) => Render();
        _timer.Start();
    }

    void Render()
    {
        _frame++;
        uint color = 0xFF000000u | ((uint)((_frame * 3) & 255) << 16) | (0x40u << 8) | (uint)(255 - (_frame & 255));
        _dev.Clear(0, IntPtr.Zero, 0x00000001, color, 1f, 0);
        _dev.BeginScene();
        _dev.EndScene();
        _dev.Present(IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
        if ((_frame % 30) == 0)
            _label.Text = "D3D turbo #" + _frame + "\nLeave open while review runs";
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.Run(new GpuTurboD3D());
    }
}
"@ -ReferencedAssemblies System.Windows.Forms, System.Drawing

[GpuTurboD3D]::Main()
