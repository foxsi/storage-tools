import sys, datetime, os

import numpy as np
import matplotlib as mpl
from matplotlib import pyplot as plt

import tqdm

code_ext = ['.c', '.cpp', '.h', '.hpp', '.py', '.jl', '.pro', '.sh', '.m', '.ipynb', '.service', '.fl', '.o', '.a', '.exe', '.pkl', '.xml']
data_ext = ['.pcap', '.pcapng', '.dat', '.tpx', '.fits', '.mat', '.d', '.mca', '', '.log', '.root', '.csv', '.zip']
cad_ext = ['.easm', '.dxf', '.step', '.stp', '.sldprt', '.sldasm', '.x_']
doc_ext = ['.xls', '.ppt', '.doc', '.xlsx', '.pptx', '.docx', '.drawio', '.key', '.gan', '.rtf', '.txt', '.pdf']
img_ext = ['.png', '.jpeg', '.jpg', '.tiff', '.heic']
mov_ext = ['.mp4', '.mov', '.mpg', '.avi']

def dt2f(date, epoch=datetime.datetime(1970,1,1,0,0,0)):
    return (date - epoch).total_seconds()
def f2dt(total_seconds, epoch=datetime.datetime(1970,1,1,0,0,0)):
    return epoch + datetime.timedelta(seconds=total_seconds)
    
class FileData:
    def __init__(self, category, size, date):
        self.category = category
        self.size = size
        self.date = date

class FileSet:
    def __init__(self, categories):
        self.categories = [cat for cat in categories if cat.filter is not None]
        self.nocat = next(cat for cat in categories if cat.filter is None)

    def get_cat(self, ext):
        for cat in self.categories:
            if ext in cat.filter:
                return cat

        return self.nocat
        
    def push(self, ext, size):
        for cat in self.categories:
            success = cat.push(ext, size)
            if success:
                return cat
        if not success:
            self.nocat.push(ext, size)
            return self.nocat

    def to_string(self, unit='B'):
        outstr = ''
        for cat in [self.nocat] + self.categories:
            outstr += '\n' + cat.name + ':\n> total size: ' + "{:9.4f}".format(cat.size / get_unit(unit)[0]) + ' ' + get_unit(unit)[1]
            outstr += '\n> sizeless files: ' + str(cat.nosize)

        outstr += '\n'
        return outstr

class FileCategory:
    def __init__(self, name, filter=None):
        self.name = name
        self.filter = filter
        self.size = 0
        self.nosize = 0

    def push(self, ext, size):
        if self.filter is not None:
            if ext in self.filter:
                if size == -1:
                    self.nosize += 1
                else:
                    self.size += size
                return True
            else:
                return False
        else:
            if size == -1:
                self.nosize += 1
            else:
                self.size += size
            return True

def get_unit(unit):
    if unit == 'B':
        return (1.0, unit)
    elif unit == 'kB':
        return (1e3, unit)
    elif unit == 'MB':
        return (1e6, unit)
    elif unit == 'GB':
        return (1e9, unit)
    elif unit == 'TB':
        return (1e12, unit)

def display_ext(ext_data, unit='B'):
    outstr = ''
    for key in ext_data.keys():
        outstr += '\n' + "{:>20}".format(key) + ' : ' + "{:9.4f}".format(ext_data[key] / get_unit(unit)[0]) + ' ' + get_unit(unit)[1]
    outstr += '\n'
    return outstr

def get_path(lsline):
    # there are four items in the ls: size, date, time, filename.
    # this way we avoid splitting the path name, which may have spaces.
    return lsline.split(maxsplit=3)[-1]
    
def get_ext(lsline):
    pathname = get_path(lsline)
    basename = pathname.rsplit(sep='/', maxsplit=1)[-1].rstrip()
    ext = os.path.splitext(basename)[1]
    # identify file extensions
    if '.' in basename:
        ext_pos = basename.rfind('.')
        ext = basename[ext_pos::].lower()
    else:
        ext = ''
    return ext

def get_size(lsline):
    try:
        chunks = lsline.split(maxsplit=3)
        size = int(chunks[0], base=10)
    except ValueError:
        size = -1
        print("sizeless line: \"", lsline.rstrip(), end='\"\n')
    return size

def get_modtime(lsline):
    try:
        chunks = lsline.split(maxsplit=3)
        dt = datetime.datetime.strptime(chunks[1] + ' ' + chunks[2][0:15], '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        dt = datetime.datetime(1970, 1, 1, 0, 0, 0)
        print("dateless line: \"", lsline.rstrip(), end='\"\n')
    return dt
    
if __name__ == "__main__":
    
    ls_file = sys.argv[1]
    save_dir = sys.argv[2]
    if not os.path.isdir(save_dir):
        print('pass in two args: a file with output of `rclone lsl`, and a folder to save plots to.')
        exit(-1)
    
    file_categories = [
        FileCategory('Code', code_ext),
        FileCategory('Raw data', data_ext),
        FileCategory('CAD', cad_ext),
        FileCategory('Documents', doc_ext),
        FileCategory('Pictures', img_ext),
        FileCategory('Movies', mov_ext),
        FileCategory('Uncategorized')
    ]
    file_set = FileSet(file_categories)

    all_sizes = []
    all_dates = []
    all_data = []

    
    # Source - https://stackoverflow.com/a/1019572    
    linecount = sum(1 for _ in open(ls_file, 'r'))

    with open(ls_file, 'r') as f:
        total_size = 0
        sizeless_count = 0
        total_count = 0
        exts = set()
        exts_sizes = {}
        csvlines = []
        
        for k,line in enumerate(tqdm.tqdm(f, desc='ingesting ls...', total=linecount)):
            
            # count all files
            total_count += 1

            # pull the file extension off
            ext = get_ext(line)
            # report size in bytes
            size = get_size(line)

            dt = get_modtime(line)
            path = get_path(line)

            # thiscsvline = ''
            thiscsvline = 'n' + ';' + str(size) + ';' + dt.strftime('%Y-%m-%d %H:%M:%S.%f') + ';' + path
            csvlines.append(thiscsvline)

            # add this to the list of known extensions
            if ext not in exts:
                exts.add(ext)
                exts_sizes[ext] = 0
                
            file_set.push(ext, size)
            
            # if the size is reported, account it
            if size != -1:
                total_size += size
                exts_sizes[ext] += size
                all_sizes.append(size)
                all_dates.append(dt)
                all_data.append(FileData(category=file_set.get_cat(ext).name, size=size, date=dt))
            else:
                sizeless_count += 1

        # sort file size data 
        exts_sizes = dict(sorted(exts_sizes.items(), key=lambda item: item[1], reverse=True))
        with open(os.path.join(save_dir, 'ls.csv'), 'w') as f:
            f.write(''.join(csvlines))

        print('\nSize by extension -----------------')
        print(display_ext(exts_sizes, unit='GB'))

        print('Totals ----------------------------')
        print(f"total size: \x1b[32m{total_size/1e9} GB\x1b[0m")
        print(f"found \x1b[32m{sizeless_count} out of {total_count} files\x1b[0m without a size")
        
        print('By filetype -----------------------')
        print(file_set.to_string(unit='GB'))

    datesindex = np.array(all_dates).argsort()
    dates = np.array(all_dates)[datesindex]
    sizes = np.array(all_sizes)[datesindex] / 1e9
    sizes = np.cumsum(sizes)

    # restructure the (type, date, size) data into per-type:
    typewise = {}
    for el in all_data:
        if el.category not in typewise.keys():
            typewise[el.category] = {'dates': [el.date]}
            typewise[el.category]['sizes'] = [el.size]
        else:
            typewise[el.category]['dates'].append(el.date)
            typewise[el.category]['sizes'].append(el.size)

    # sort by date, then cumsum size:
    for key in typewise.keys():
        datesindex = np.array(typewise[key]['dates']).argsort()
        typewise[key]['dates'] = np.array(typewise[key]['dates'])[datesindex]
        typewise[key]['sizes'] = np.array(typewise[key]['sizes'])[datesindex] / 1e9
        typewise[key]['sizes'] = np.cumsum(typewise[key]['sizes'])

    typewise_fulltime = {}
    stack_sizes = np.zeros(shape=(len(dates), len(typewise.keys())))
    for k,key in enumerate(typewise.keys()):
        fdates = [dt2f(d) for d in dates]
        sdates = [dt2f(d) for d in typewise[key]['dates']]
        inner = {'dates': dates}
        inner['sizes'] = np.interp(fdates, sdates, typewise[key]['sizes'])
        typewise_fulltime[key] = inner
        stack_sizes[:, k] = inner['sizes']
    
    fig, ax = plt.subplots(1,1,figsize=(7,5))
    ax.plot(dates, sizes, linewidth=1, color='black', label='Total')
    ax.set_xlim([datetime.datetime(2009, 1,1,0,0,0), datetime.datetime(2027, 1,1,0,0,0)])
    ax.set_xlabel('Time')
    ax.set_ylabel('Total Drive Storage [GB]')
    ax.set_title('FOXSI Google Drive Storage')
    ax.grid(visible=True, which='major', axis='both')
    ax.stackplot(dates, stack_sizes.T, labels=typewise.keys())
    ax.legend()
    
    fig.savefig(os.path.join(save_dir, 'historical-linear.pdf'), transparent=True)

    fig, ax = plt.subplots(1,1,figsize=(7,5))
    ax.plot(dates, sizes, linewidth=1, color='black', label='Total')
    ax.set_xlim([datetime.datetime(2009, 1,1,0,0,0), datetime.datetime(2027, 1,1,0,0,0)])
    ax.set_xlabel('Time')
    ax.set_ylabel('Total Drive Storage [GB]')
    ax.set_title('FOXSI Google Drive Storage')
    ax.grid(visible=True, which='major', axis='both')
    for key in typewise.keys():
        ax.plot(typewise[key]['dates'], typewise[key]['sizes'], label=key)
    ax.set_yscale('log')
    ax.set_ylim([1e-2, 1e4])
    ax.legend()
    fig.savefig(os.path.join(save_dir, 'historical-log.pdf'), transparent=True)
    
    
    plt.show()