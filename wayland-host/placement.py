"""Monitor/phone layout in desktop logical coordinates, shared by all backends.

The phone rectangle may extend beyond a corner. Only its intersection with the
selected monitor edge captures input; mapping retains the hidden phone portion.
"""
import math


def validate(value):
    if not isinstance(value,dict):return None
    try:
        offset=float(value['offset']);size=float(value['size'])
        monitor=tuple(value['monitor'])
        if len(monitor)!=4 or any(not isinstance(v,int) for v in monitor):return None
        if monitor[0]<=0 or monitor[1]<=0:return None
        if not all(math.isfinite(v) for v in (offset,size)):return None
        if not .001<=size<=20 or offset+size<=0 or offset>=1:return None
        return dict(offset=offset,size=size,monitor=list(monitor))
    except (KeyError,TypeError,ValueError):return None


def geometry(zones,edge,layout=None):
    extrema={'right':lambda z:z[2]+z[0],'left':lambda z:-z[2],
             'bottom':lambda z:z[3]+z[1],'top':lambda z:-z[3]}
    if not zones:raise ValueError('No desktop monitors found')
    if layout:
        layout=validate(layout)
        if not layout:raise ValueError('Invalid phone placement')
        zone=tuple(layout['monitor'])
        if zone not in zones:raise ValueError('Monitor layout changed. Reposition the phone before sharing.')
    else:zone=max(zones,key=extrema[edge])
    w,h,x,y=zone;length=h if edge in ('left','right') else w
    origin=y if edge in ('left','right') else x
    offset=layout['offset'] if layout else 0
    size=layout['size'] if layout else 1
    start=origin+offset*length;span=size*length
    lo=max(origin,math.ceil(start));hi=min(origin+length-1,math.ceil(start+span)-1)
    if hi<=lo:raise ValueError('Phone must overlap at least two logical pixels of the monitor edge')
    lines={'right':(x+w,lo,x+w,hi),'left':(x,lo,x,hi),
           'bottom':(lo,y+h,hi,y+h),'top':(lo,y,hi,y)}
    return zone,lines[edge],start,span


def phone_rect(edge,offset,size,w,h):
    # Portrait phone silhouette. Size is a visual ratio, adjustable by the user.
    ph=size*h if edge in ('left','right') else size*w/.46
    pw=ph*.46
    return {'right':(w,offset*h,pw,ph),'left':(-pw,offset*h,pw,ph),
            'bottom':(offset*w,h,pw,ph),'top':(offset*w,-ph,pw,ph)}[edge]


def dragged(x,y,w,h,height):
    # Snap to the nearest edge; preserve off-corner placement.
    distances={'left':abs(x),'right':abs(x-w),'top':abs(y),'bottom':abs(y-h)}
    edge=min(distances,key=distances.get)
    span=height if edge in ('left','right') else height*.46
    length=h if edge in ('left','right') else w
    center=y if edge in ('left','right') else x
    offset=max(-span+2,min(length-2,center-span/2))/length
    return edge,offset,span/length
