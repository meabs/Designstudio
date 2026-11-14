"""Synthesises an original ambient bed (soft pads + gentle arpeggio) so the video needs no licensed music. Output: public/music.mp3"""
import subprocess, sys, os
FF = os.environ.get('FFMPEG', 'ffmpeg')
chords = [  # (pad notes, arp notes)
    ([110.00, 164.81, 196.00, 261.63], [220.00, 329.63, 392.00, 523.25]),   # Am7
    ([87.31, 130.81, 174.61, 220.00], [174.61, 261.63, 349.23, 440.00]),    # Fmaj7
    ([130.81, 196.00, 261.63, 329.63], [261.63, 392.00, 523.25, 659.25]),   # C
    ([98.00, 146.83, 196.00, 246.94], [196.00, 293.66, 392.00, 493.88]),    # G6
]
D, STEP = 14.0, 10.5
inputs, filt, labels = [], [], []
n = 0
for k, (pad, arp) in enumerate(chords):
    for f in pad:
        inputs += ['-f', 'lavfi', '-t', str(D), '-i', f'sine=f={f}:r=44100']; filt.append(f'[{n}]volume=0.09,afade=t=in:d=4,afade=t=out:st={D-4}:d=4,adelay={int(k*STEP*1000)}|{int(k*STEP*1000)}[a{n}]'); labels.append(f'[a{n}]'); n += 1
    N = lambda i: arp[i]
    expr = f"0.16*sin(2*PI*if(lt(mod(t,3),0.75),{N(0)},if(lt(mod(t,3),1.5),{N(1)},if(lt(mod(t,3),2.25),{N(2)},{N(3)})))*t)*exp(-4.5*mod(t,0.75))*(1-exp(-300*mod(t,0.75)))"
    inputs += ['-f', 'lavfi', '-t', str(D), '-i', f"aevalsrc=exprs='{expr}':sample_rate=44100:channel_layout=mono"]
    filt.append(f'[{n}]afade=t=in:d=3,afade=t=out:st={D-3}:d=3,adelay={int(k*STEP*1000)}|{int(k*STEP*1000)}[a{n}]'); labels.append(f'[a{n}]'); n += 1
total = (len(chords) - 1) * STEP + D
graph = ';'.join(filt) + ';' + ''.join(labels) + f'amix=inputs={n}:normalize=0,lowpass=f=2600,aecho=0.8:0.6:420|700:0.35|0.25,tremolo=f=0.12:d=0.25,volume=1.4,alimiter=limit=0.9[m]'
base = 'public/_bed.wav'
subprocess.check_call([FF, '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[m]', '-ac', '2', base])
# loop to ~120 s with a smooth tail
subprocess.check_call([FF, '-v', 'error', '-y', '-stream_loop', '3', '-i', base, '-t', '120', '-af', 'volume=11dB,alimiter=limit=0.85,afade=t=out:st=114:d=6', '-b:a', '160k', 'public/music.mp3'])
os.remove(base); print('music ok', round(total), 's loop ->120s')
