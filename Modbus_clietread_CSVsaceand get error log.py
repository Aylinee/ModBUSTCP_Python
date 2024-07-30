import tkinter as tk
from tkinter import ttk, messagebox
from pymodbus.client.sync import ModbusTcpClient
import pandas as pd
import os
from datetime import datetime
import time

#I have 2 devices and I need connect together if you have only 1 device could you please delete 1 IP
DEVICE_IP_LEFT = 'xxx.xxx.xxx.xxx'  # first device IP
DEVICE_IP_RIGHT = 'xxx.xxx.xxx.xxx'  # second device IP 
DEVICE_PORT = 502  # Modbus TCP port number

# Modbus ddreses and formats
MODBUS_ADDRESSES = {
    'program_number': (0x2201, 'short'),
    'fifo_count': (0x2202, 'short'),
    'test_type': (0x2203, 'short'),
    'status_info': (0x2204, 'short'),
    'step_code': (0x2205, 'short'),
    'low_pressure': (0x2206, 'float'),
    'high_pressure': (0x2207, 'float'),
    'low_pressure_unit': (0x2208, 'short'),
    'high_pressure_unit': (0x2209, 'short'),
    'low_flow': (0x220A, 'float'),
    # uou can change name and adding much more than 
}

previous_values_left = {}
previous_values_right = {}

def read_modbus_data(client, address, data_type):
    try:
        if data_type == 'short':
            result = client.read_holding_registers(address, 1)
            if result.isError():
                return None, f"Error reading address {address}"
            else:
                return result.registers[0], None
        elif data_type == 'float':
            result = client.read_holding_registers(address, 2)
            if result.isError():
                return None, f"Error reading address {address}"
            else:
                # 32-bit float (2x 16-bit registers)
                float_value = result.registers[0] + (result.registers[1] << 16)
                return float_value, None
        else:
            return None, f"Unsupported data type: {data_type}"
    except Exception as e:
        return None, f"Exception occurred while reading address {address}: {str(e)}"

def read_device_data(device_ip, previous_values):
    client = ModbusTcpClient(device_ip, port=DEVICE_PORT)
    data = {}
    errors = []
    changes = []

    if client.connect():
        for desc, (address, data_type) in MODBUS_ADDRESSES.items():
            value, error = read_modbus_data(client, address, data_type)
            if value is not None:
                data[desc] = value
                if previous_values.get(desc) != value:
                    changes.append((desc, previous_values.get(desc), value))
                    previous_values[desc] = value
            else:
                data[desc] = 'Error'
                if error:
                    errors.append(f"{desc} (address {address}): {error}")
        client.close()
    else:
        error_message = f"Failed to connect to {device_ip}"
        errors.append(error_message)
        client.close()
    
    return data, errors, changes

def save_to_csv(device_data, errors, device_name):
    # available file path
    base_path = os.path.dirname(os.path.abspath(__file__))
    # 'modbus_data' file created
    data_folder = os.path.join(base_path, 'modbus_data')
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    
    # file folder name daily
    today = datetime.now().strftime('%Y%m%d')
    file_path = os.path.join(data_folder, f'{device_name}_modbus_data_{today}.csv')
    
    # Sace CSV file
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = {'Timestamp': [timestamp]}
    for key, value in device_data.items():
        data[key] = [value]
    df = pd.DataFrame(data)
    
    # If you have already file use it
    if os.path.exists(file_path):
        df_existing = pd.read_csv(file_path)
        df_combined = pd.concat([df_existing, df])
        df_combined.to_csv(file_path, index=False)
    else:
        df.to_csv(file_path, index=False)
    
    # Get error log
    log_path = os.path.join(data_folder, f'{device_name}_error_log_{today}.txt')
    if errors:
        with open(log_path, 'a') as log_file:
            for error in errors:
                log_file.write(f"{timestamp}: {error}\n")
                # get error mesaage via pup up
                messagebox.showerror("Error", error)

def save_changes_to_csv(changes, device_name):
    base_path = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(base_path, 'modbus_data')
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    
    today = datetime.now().strftime('%Y%m%d')
    file_path = os.path.join(data_folder, f'{device_name}_modbus_changes_{today}.csv')
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = {'Timestamp': [timestamp]}
    for desc, from_value, to_value in changes:
        data[desc] = [f"{from_value} -> {to_value}"]
    df = pd.DataFrame(data)
    
    if os.path.exists(file_path):
        df_existing = pd.read_csv(file_path)
        df_combined = pd.concat([df_existing, df])
        df_combined.to_csv(file_path, index=False)
    else:
        df.to_csv(file_path, index=False)

def fetch_and_save_data():
    global previous_values_left, previous_values_right
    while True:
        left_data, left_errors, left_changes = read_device_data(DEVICE_IP_LEFT, previous_values_left)
        right_data, right_errors, right_changes = read_device_data(DEVICE_IP_RIGHT, previous_values_right)
        
        save_to_csv(left_data, left_errors, "Left_Device")
        save_to_csv(right_data, right_errors, "Right_Device")
        
        if left_changes:
            save_changes_to_csv(left_changes, "Left_Device")
        if right_changes:
            save_changes_to_csv(right_changes, "Right_Device")
        
       # time.sleep(60)  # If you need wait to update delete # it will be 60 sec wait and get new data

def create_gui():
    root = tk.Tk()
    root.title("Modbus Data Reader")

    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    fetch_button = ttk.Button(frame, text="Start Fetching Data", command=lambda: start_fetching_data(root))
    fetch_button.grid(row=0, column=0, padx=10, pady=10)

    quit_button = ttk.Button(frame, text="Quit", command=root.destroy)
    quit_button.grid(row=0, column=1, padx=10, pady=10)

    root.mainloop()

def start_fetching_data(root):
    # new thread for get back data
    import threading
    data_thread = threading.Thread(target=fetch_and_save_data, daemon=True)
    data_thread.start()
    messagebox.showinfo("Info", "Started fetching data in the background.")

if __name__ == "__main__":
    create_gui()
