#!/usr/bin/env python3
import sys
import threading
import tkinter as tk
import time
from os import getenv
from os.path import abspath
from typing import Callable, Dict
from tkinter.filedialog import asksaveasfilename,askopenfilename
from tkinter import ttk,messagebox
import pygame as py
import pickle

from PIL import Image, ImageTk

sys.path.append(abspath('./'))

import chess
FEN = chess.STARTING_FEN
from ai import Searcher

modify_fen = [["rnbakabnr","rnbakabn1","1nbakabnr","1nbakabn1"],["rnbakab1r","rnbakab2","1nbakab1r","1nbakab2"],
["r1bakabnr","r1bakabn1","2bakabnr","2bakabn1"],["r1bakab1r","r1bakab2","2bakab1r","2bakab2"],["/9/1c5c1/","/9/1c7/","/9/7c1/","/9/9/"]]


SELF_PLAY, COMPUTER_PLAY = 1, 2
check_hash = 0x6414564fff
THINK_TIME = int(getenv("THINK_TIME")) if getenv("THINK_TIME") else 1
level = ('简单','普通','困难')





class ThinkThread(threading.Thread):
    def __init__(self, searcher: Searcher,think_time: int, on_finish: Callable,level: int):
        threading.Thread.__init__(self)
        self.searcher = searcher
        self.think_time = think_time
        self.on_finish = on_finish
        self.depth = 4 + level*2

    def run(self):
        move, num = self.searcher.search(THINK_TIME,self.depth)
        if self.on_finish:
            self.on_finish(move,num)

    def stop(self):
        self.on_finish = None


class PhotoImage(ImageTk.PhotoImage):
    @classmethod
    def open(cls, fp):
        return cls(Image.open(fp))

    @classmethod
    def open_and_crop(cls, fp, x, y, w, h):
        im = Image.open(fp)
        im = im.crop((x, y, x + w, y + h))
        return cls(im)


def lock_control(a_func):
    def wrapTheFunction(self):
        if self.lock:
            return
        else:
            self.lock = True
            a_func(self)
    return wrapTheFunction


class Application(tk.Frame):

    resources: Dict[str, PhotoImage]
    style = {"start_x": 15, "start_y": 45, "space_x": 60, "space_y": 60}
    select_square: chess.Square = None
    board: chess.Board
    rotate = False
    mode = SELF_PLAY
    lock = False


    def __init__(self) -> None:
        self.master = tk.Tk()
        super().__init__(self.master)
        
        self.load_resources()
        py.mixer.init()#加载背景音乐
        py.mixer.music.load(r'.\assets\chess.mp3')
        py.mixer.music.play(-1, 10)
        self.master.title("中国象棋")
        self.master.resizable(False, False)
        self.master.geometry('+%d+%d' % ((self.master.winfo_screenwidth() - 570) / 2,(self.master.winfo_screenheight() - 690) / 2))  # center window on desktop
        self.grid()
        self.com_side = False
        self.level = 1
        self.searcher = Searcher()
        self.create_widgets()
        
        self.open_black = tk.BooleanVar(self)
        self.open_red = tk.BooleanVar(self)
        self.open_red.set(False)
        self.open_black.set(False)
        self.options_frame = tk.Toplevel(self, borderwidth=20)
        self.confirm_reset()


    def destroy_frame(self):
        self.options_frame.destroy()
        self.lock = False

    def load_resources(self) -> None:
        self.resources = {}
        self.resources["bg"] = PhotoImage.open("./assets/board.png")
        self.resources["bg_r"] = PhotoImage.open("./assets/board_rotate.png")
        all_pieces = ["R", "N", "B", "A", "K", "C", "P", "r", "n", "b", "a", "k", "c", "p", "red_box", "blue_box"]
        for offset, piece in enumerate(all_pieces):
            self.resources[piece] = PhotoImage.open_and_crop("./assets/pieces.png", 0, offset * 60, 60, 60)
        self.resources["checkmate"] = PhotoImage.open("./assets/checkmate.png")
        self.resources["checkmate_1"] = PhotoImage.open("./assets/checkmate_1.png")
        self.resources["check"] = PhotoImage.open("./assets/check.png")
        self.resources["bg_o"] = PhotoImage.open("./assets/bg.png")

    @lock_control
    def save_chess(self) -> None:
        filenewpath = asksaveasfilename(title=u'保存文件', filetypes=[("PKL文件", "*.pkl"),("ALL Files","*.*")],defaultextension = 'pkl',initialfile = 'chess', initialdir=('./'))   # 设置保存文件，并返回文件名
        if(filenewpath != ''):  
            f = open(filenewpath, 'wb')
            pickle.dump((self.com_side,self.mode,self.rotate,self.board.fen(),
                self.board.move_stack,self.board._stack,self.select_square,self.black_count,self.red_count,self.level,check_hash), f)
            f.close()
        self.lock = False
    
    
    def load_chess(self) -> None:
        
        filepath = askopenfilename(title=u'打开文件', filetypes=[("PKL文件", "*.pkl"),("ALL Files","*.*")],defaultextension = 'pkl',initialfile = 'chess.pkl', initialdir=('./'),parent=self.options_frame)  # 选择打开什么文件，返回文件名
        if(filepath == ''): return
        self.insert("加载棋局··")
        try:
            f = open(filepath, 'rb')
            info = pickle.load(f)
            f.close()
            f = None
            if((len(info) != 11) or (info[-1] != check_hash)):
                raise Exception("load fails!")
            (self.com_side,self.mode,self.rotate,fen,
                self.board.move_stack,self.board._stack,self.select_square,self.black_count,self.red_count,self.level,_) = info
            self.board.set_fen(fen)
            self.to_check = True
            self.GG = False
            if self.n_set.current():
                self.mode = self.n_set.current()
                if self.mode > 1:
                    self.level = self.mode - 2
                    self.mode = 2
                self.com_side = not self.board.turn
                self.board.move_stack,self.board._stack = [],[]
                self.select_square = None
                self.black_count,self.red_count = 0,0
            self.insert("加载成功")
            if self.mode == COMPUTER_PLAY:
                self.insert("当前模式—人机对战")
                self.insert("难度-"+level[self.level])
            else:
                self.insert("当前模式—本地双人")
            self.update_canvas()
        except:
            if(f):
                f.close()
            messagebox.showwarning('加载失败','棋局文件错误')
            self.insert("加载失败,请打开正确的文件","warning")
        self.destroy_frame()

    @lock_control
    def load_option(self)-> None:
        self.options_frame = tk.Toplevel(self, borderwidth=20)
        x = self.master.winfo_x()
        y = self.master.winfo_y()
        self.options_frame.geometry("+%d+%d" % (x + 200, y + 200))
        self.options_frame.resizable(False, False)
        self.options_frame.protocol('WM_DELETE_WINDOW',self.destroy_frame)

        label = tk.Label(self.options_frame, text="加载模式:")
        label.grid(row=0, column=0)
        self.n_set = ttk.Combobox(self.options_frame,state= "readonly", width=16)
        self.n_set.grid(row=0, column=1,columnspan=3)
        self.n_set['value'] = ('正常','残局(本地双人)','残局(人机对战-简单)','残局(人机对战-普通)','残局(人机对战-困难)')
        self.n_set.current(0)
        start_button = tk.Button(self.options_frame, text="确定", command=self.load_chess)
        start_button.grid(row=1, column=0, columnspan=2)
        cancel_button = tk.Button(self.options_frame, text="取消", command=self.destroy_frame)
        cancel_button.grid(row=1, column=2, columnspan=2)
        self.options_frame.update()

    def create_widgets(self) -> None:
        self.bg = tk.Canvas(self, bg="white", height=690, width=200, highlightthickness=0)
        self.bg.grid(row=0,column=100,rowspan=100,columnspan=40)
        self.canvas = tk.Canvas(self, bg="white", height=690, width=570, highlightthickness=0)
        self.canvas.bind("<Button-1>", self.handle_click)
        self.button0 = tk.Button(self, text="翻转棋盘", command=self.rotate_board)
        self.button1 = tk.Button(self, text="悔棋", command=self.pop)
        self.button2 = tk.Button(self, text="本地双人", command=self.confirm_options)
        self.button3 = tk.Button(self, text="人机对战", command=self.show_options)
        self.button4 = tk.Button(self, text="保存棋局", command=self.save_chess)
        self.button5 = tk.Button(self, text="加载棋局", command=self.load_option)
        self.canvas.grid(row=0,column=0,rowspan=100,columnspan=100)
        self.bg.create_image(0, 0, image=self.resources["bg_o"], anchor="nw")
        self.button0.grid(row=53,column=101, padx=20, pady=5)
        self.button1.grid(row=53,column=102, padx=20, pady=5)
        self.button2.grid(row=55,column=101, padx=20, pady=5)
        self.button3.grid(row=55,column=102, padx=20, pady=5)
        self.button4.grid(row=57,column=101, padx=20, pady=5)
        self.button5.grid(row=57,column=102, padx=20, pady=5)

        tk.Label(self, text="消息记录",font=('楷体',14)).grid(row=71, column=101,columnspan=2)
        self.text =tk.Text(self, width=20, heigh=15)
        self.text.bind("<Key>", lambda a: "break")
        self.text.grid(row=72,column=101, columnspan=2)
        self.text.tag_configure("warning", foreground="red")
        
    def insert(self,message,tags=None):
        self.text.insert(tk.END,message+"\n",tags)
        self.text.see(tk.END)
    
    @lock_control
    def show_options(self) -> None:
        self.options_frame = tk.Toplevel(self, borderwidth=20)
        x = self.master.winfo_x()
        y = self.master.winfo_y()
        self.options_frame.geometry("+%d+%d" % (x + 200, y + 200))
        self.options_frame.resizable(False, False)
        self.options_frame.protocol('WM_DELETE_WINDOW',self.destroy_frame)
        self.computer_side = tk.BooleanVar(self)

        label = tk.Label(self.options_frame, text="电脑执子:")
        label.grid(row=0, column=0)
        red_button = tk.Radiobutton(self.options_frame, text="红", variable=self.computer_side, value=chess.RED)
        red_button.grid(row=0, column=1)
        black_button = tk.Radiobutton(self.options_frame, text="黑", variable=self.computer_side, value=chess.BLACK)
        black_button.select()
        black_button.grid(row=0, column=2)

        label = tk.Label(self.options_frame, text="电脑强度:")
        label.grid(row=1, column=0)
        self.level_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.level_set.grid(row=1, column=1,columnspan=3)
        self.level_set['value'] = ('简单','普通','困难')
        self.level_set.current(1)

        tk.Label(self.options_frame, text="让子设定",font=('楷体',14)).grid(row=2, column=0,columnspan=4)
        label = tk.Label(self.options_frame, text="黑方让子:")
        label.grid(row=3, column=0)
        black_on = tk.Radiobutton(self.options_frame, text="是", variable=self.open_black, value=True)
        black_on.grid(row=3, column=1)
        black_off = tk.Radiobutton(self.options_frame, text="否", variable=self.open_black, value=False)
        black_off.grid(row=3, column=2)
        black_off.select()

        label = tk.Label(self.options_frame, text="红方让子:")
        label.grid(row=4, column=0)
        red_on = tk.Radiobutton(self.options_frame, text="是", variable=self.open_red, value=True)
        red_on.grid(row=4, column=1)
        red_off = tk.Radiobutton(self.options_frame, text="否", variable=self.open_red, value=False)
        red_off.grid(row=4, column=2)
        red_off.select()
        
        label = tk.Label(self.options_frame, text="让车设定:")
        label.grid(row=5, column=0)
        self.r_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.r_set.grid(row=5, column=1,columnspan=3)
        self.r_set['value'] = ('不让车','让左车','让右车','让双车')
        self.r_set.current(0)


        label = tk.Label(self.options_frame, text="让马设定:")
        label.grid(row=6, column=0)
        self.n_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.n_set.grid(row=6, column=1,columnspan=3)
        self.n_set['value'] = ('不让马','让左马','让右马','让双马')
        self.n_set.current(0)

        label = tk.Label(self.options_frame, text="让炮设定:")
        label.grid(row=7, column=0)
        self.c_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.c_set.grid(row=7, column=1,columnspan=3)
        self.c_set['value'] = ('不让炮','让左炮','让右炮','让双炮')
        self.c_set.current(0)


        start_button = tk.Button(self.options_frame, text="开始挑战", command=self.start_game)
        start_button.grid(row=8, column=0, columnspan=2)
        cancel_button = tk.Button(self.options_frame, text="取消挑战", command=self.destroy_frame)
        cancel_button.grid(row=8, column=2, columnspan=2)
        self.options_frame.update()

    @lock_control
    def confirm_options(self) -> None:
        self.options_frame = tk.Toplevel(self, borderwidth=20)
        x = self.master.winfo_x()
        y = self.master.winfo_y()
        self.options_frame.geometry("+%d+%d" % (x + 200, y + 200))
        self.options_frame.resizable(False, False)
        self.options_frame.protocol('WM_DELETE_WINDOW',self.destroy_frame)

        
        tk.Label(self.options_frame, text="让子设定",font=('楷体',14)).grid(row=1, column=0,columnspan=4)
        label = tk.Label(self.options_frame, text="黑方让子:")
        label.grid(row=2, column=0)
        black_on = tk.Radiobutton(self.options_frame, text="是", variable=self.open_black, value=True)
        black_on.grid(row=2, column=1)
        black_off = tk.Radiobutton(self.options_frame, text="否", variable=self.open_black, value=False)
        black_off.grid(row=2, column=2)
        black_off.select()

        label = tk.Label(self.options_frame, text="红方让子:")
        label.grid(row=3, column=0)
        red_on = tk.Radiobutton(self.options_frame, text="是", variable=self.open_red, value=True)
        red_on.grid(row=3, column=1)
        red_off = tk.Radiobutton(self.options_frame, text="否", variable=self.open_red, value=False)
        red_off.grid(row=3, column=2)
        red_off.select()
        
        label = tk.Label(self.options_frame, text="让车设定:")
        label.grid(row=4, column=0)
        self.r_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.r_set.grid(row=4, column=1,columnspan=3)
        self.r_set['value'] = ('不让车','让左车','让右车','让双车')
        self.r_set.current(0)


        label = tk.Label(self.options_frame, text="让马设定:")
        label.grid(row=5, column=0)
        self.n_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.n_set.grid(row=5, column=1,columnspan=3)
        self.n_set['value'] = ('不让马','让左马','让右马','让双马')
        self.n_set.current(0)

        label = tk.Label(self.options_frame, text="让炮设定:")
        label.grid(row=6, column=0)
        self.c_set = ttk.Combobox(self.options_frame,state= "readonly", width=14)
        self.c_set.grid(row=6, column=1,columnspan=3)
        self.c_set['value'] = ('不让炮','让左炮','让右炮','让双炮')
        self.c_set.current(0)

        start_button = tk.Button(self.options_frame, text="开始挑战", command=self.confirm_reset)
        start_button.grid(row=7, column=0, columnspan=2)
        cancel_button = tk.Button(self.options_frame, text="取消挑战", command=self.destroy_frame)
        cancel_button.grid(row=7, column=2, columnspan=2)
        self.options_frame.update()

    def start_game(self) -> None:
        self.level = self.level_set.current()
        self.set_board()
        self.mode = COMPUTER_PLAY
        self.insert("开始对战—人机对战")
        self.insert("难度-"+level[self.level])
        self.com_side = self.computer_side.get()
        if self.com_side == chess.RED:
            self.rotate = True
            self.update_canvas()
            self.computer_move()
        else:
            self.rotate = False
            self.update_canvas()

    def confirm_reset(self) -> None:
        self.insert("开始对战—本地双人")
        self.set_board()
        self.update_canvas()
        self.mode = SELF_PLAY
    
    def get_board(self):
        return modify_fen[self.n_set.current()][self.r_set.current()]+modify_fen[4][self.c_set.current()]

    
    def set_board(self) -> None:
        if(self.open_red.get() or self.open_black.get()):
            basefen = self.get_board()
            new_fen = (basefen if self.open_black.get() else "rnbakabnr/9/1c5c1/") + "p1p1p1p1p/9/9/P1P1P1P1P"+((basefen.upper())[::-1] if self.open_red.get() else "/1C5C1/9/RNBAKABNR") + " w - - 0 1"
            self.board = chess.Board(new_fen)
        else: self.board = chess.Board(FEN)
        self.destroy_frame()
        self.select_square = None
        self.black_count = 0
        self.red_count = 0
        self.to_check = False
        self.GG = False


    def rotate_board(self) -> None:
        self.rotate = not self.rotate
        self.update_canvas()





    def pop(self) -> None:
        # if self.board.is_checkmate(): #虽然游戏结束了，但仍支持悔棋
        #     return
        if self.mode == COMPUTER_PLAY :
            if self.board.turn == self.com_side:
                if not self.GG:
                    # 电脑思考时不能悔棋
                    return
            else: 
                if self.board.fullmove_number == 1:
                    return
                else:
                    self.board.pop()
        if self.board.pop():
            if(self.board.turn):
                self.red_count = self.red_count + 1
                self.insert("红方悔棋!\n红方悔棋共%d次"%self.red_count)
            else:
                self.black_count = self.black_count + 1
                self.insert("黑方悔棋!\n黑方悔棋共%d次"%self.black_count,"warning")
        self.select_square = None
        self.GG = False
        self.update_canvas()

    def computer_move(self) -> None:
        self.insert("电脑思考中··",("warning" if self.board.turn else None))
        # print(self.board.fen())
        self.start_time = time.time()
        self.searcher.set(self.board,self.board.turn)
        def on_finish(move,node_num = None):
            self.insert('思考用时%.2fs,共搜索%d个状态' % (time.time() - self.start_time,node_num),("warning" if self.board.turn else None))
            self.push(move)
        ThinkThread(self.searcher,THINK_TIME, on_finish,self.level).start()

    def handle_click(self, event: tk.Event) -> None:
        if self.GG:
            return
        square = self.get_click_square(event.x, event.y)
        piece = self.board.piece_at(square)
        if self.mode == SELF_PLAY:
            my_color = self.board.turn
        else:
            my_color = not self.com_side


        if piece and self.board.color_at(square) == my_color and my_color == self.board.turn:
            self.select_square = square
            self.update_canvas()
        elif self.select_square:
            move = chess.Move(self.select_square, square)
            if move in self.board.legal_moves:
                self.push(move)
                if self.mode == COMPUTER_PLAY and not self.GG:
                    self.computer_move()

    def push(self, move: chess.Move):
        self.insert(self.board.chinese_move(move, full_width=True),("warning" if self.board.turn else None))
        self.board.push(move)
        self.select_square = None
        self.to_check = True
        self.update_canvas()

    def rotate_square(self, square: chess.Square) -> chess.Square:
        return 255 - square - 1

    def create_piece(self, piece: chess.Piece, square: chess.Square) -> None:
        if self.rotate:
            square = self.rotate_square(square)
        x = (
            self.style["start_x"]
            + (chess.square_file(chess.SQUARES_180[square]) - 3) * self.style["space_x"]
        )
        y = (
            self.style["start_y"]
            + (chess.square_rank(chess.SQUARES_180[square]) - 3) * self.style["space_y"]
        )
        self.canvas.create_image(x, y, image=self.resources[piece.symbol()], anchor="nw")

    def create_box(self, square: chess.Square, color="blue"):
        box = "blue_box" if color == "blue" else "red_box"
        if self.rotate:
            square = self.rotate_square(square)
        x = (
            self.style["start_x"]
            + (chess.square_file(chess.SQUARES_180[square]) - 3) * self.style["space_x"]
        )
        y = (
            self.style["start_y"]
            + (chess.square_rank(chess.SQUARES_180[square]) - 3) * self.style["space_y"]
        )
        self.canvas.create_image(x, y, image=self.resources[box], anchor="nw")

    def get_click_square(self, x: int, y: int) -> chess.Square:
        file = (x - self.style["start_x"]) // self.style["space_x"] + 3
        rank = (y - self.style["start_y"]) // self.style["space_y"] + 3
        square = chess.msb(chess.BB_FILES[file] & chess.BB_RANKS[rank])
        if self.rotate:
            return self.rotate_square(chess.SQUARES_180[square])
        return chess.SQUARES_180[square]

    def update_canvas(self) -> None:
        self.canvas.delete("all")
        if self.rotate:
            self.canvas.create_image(0, 0, image=self.resources["bg_r"], anchor="nw")
        else:
            self.canvas.create_image(0, 0, image=self.resources["bg"], anchor="nw")
        for square in chess.SQUARES_IN_BOARD:
            piece = self.board.piece_at(square)
            if piece:
                self.create_piece(piece, square)
        last_move = self.board.peek()
        self.GG = False
        if self.select_square:
            self.create_box(self.select_square, color="red")
            for move in filter(lambda x: x.from_square == self.select_square, self.board.legal_moves):
                self.create_box(move.to_square)

        elif last_move:
            self.create_box(last_move.from_square)
            self.create_box(last_move.to_square)

        
        if self.to_check:
            self.to_check = False
            if self.board.is_checkmate():
                if self.board.is_check():
                    self.canvas.create_image(0, 30, image=self.resources["checkmate"], anchor="nw")
                else:
                    self.canvas.create_image(0, 30, image=self.resources["checkmate_1"], anchor="nw")
                self.GG = True
            elif self.board.is_check():
                check_image = self.canvas.create_image(0, 30, image=self.resources["check"], anchor="nw")

                def delete_check_image():
                    self.canvas.delete(check_image)

                self.canvas.after(500, delete_check_image)
        elif self.GG:
            if self.board.is_check():
                self.canvas.create_image(0, 30, image=self.resources["checkmate"], anchor="nw")
            else:
                self.canvas.create_image(0, 30, image=self.resources["checkmate_1"], anchor="nw")


if __name__ == "__main__":
    app = Application()
    app.mainloop()
